"""Admin-only analytics + notification endpoints.

All routes require `require_admin` (imported from server) — mounted on the main
`/api` router by `server.include_router()`.
"""

import os
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException

from db import db
import notifications as notif

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------- helpers ----------
def _month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def _admin_email() -> str:
    return (os.environ.get("ADMIN_EMAIL") or "").lower().strip()


async def _admin_workspace_ids() -> set:
    """Workspaces owned by the admin — excluded from conversion metrics."""
    admin = _admin_email()
    if not admin:
        return set()
    admin_user = await db.users.find_one({"email": admin}, {"_id": 0, "id": 1})
    if not admin_user:
        return set()
    ids = set()
    async for w in db.workspaces.find({"owner_id": admin_user["id"]}, {"_id": 0, "id": 1}):
        ids.add(w["id"])
    return ids


# ---------- stats overview ----------
@router.get("/stats/overview")
async def stats_overview(request: Request):
    from server import require_admin  # avoids circular import at module load
    await require_admin(request)

    month_iso = _month_start_iso()
    admin_email = _admin_email()
    admin_ws = await _admin_workspace_ids()

    total_signups = await db.users.count_documents({})
    signups_this_month = await db.users.count_documents({"created_at": {"$gte": month_iso}})

    paid_filter = {"payment_status": "paid"}
    total_paid = await db.payment_transactions.count_documents(paid_filter)
    failed_or_pending = await db.payment_transactions.count_documents({"payment_status": {"$ne": "paid"}})

    revenue_by_currency = {}
    async for doc in db.payment_transactions.aggregate([
        {"$match": paid_filter},
        {"$group": {"_id": "$currency", "amount": {"$sum": "$amount"}}},
    ]):
        revenue_by_currency[doc["_id"]] = doc["amount"] / 100
    revenue_all_time = 0
    async for doc in db.payment_transactions.aggregate([
        {"$match": paid_filter},
        {"$group": {"_id": None, "amount": {"$sum": "$amount"}}},
    ]):
        revenue_all_time = doc["amount"] / 100
    revenue_this_month = 0
    async for doc in db.payment_transactions.aggregate([
        {"$match": {**paid_filter, "updated_at": {"$gte": month_iso}}},
        {"$group": {"_id": None, "amount": {"$sum": "$amount"}}},
    ]):
        revenue_this_month = doc["amount"] / 100

    plan_counts = {"free": 0, "pro": 0, "business": 0}
    async for w in db.workspaces.aggregate([{"$group": {"_id": "$plan", "n": {"$sum": 1}}}]):
        plan_counts[w["_id"] or "free"] = plan_counts.get(w["_id"] or "free", 0) + w["n"]

    # Conversions — exclude admin-owned workspaces
    def _not_admin(ws_ids):
        return {w for w in ws_ids if w not in admin_ws}

    pro_workspaces = _not_admin(await db.payment_transactions.distinct("workspace_id", {"payment_status": "paid", "plan": "pro"}))
    business_workspaces = _not_admin(await db.payment_transactions.distinct("workspace_id", {"payment_status": "paid", "plan": "business"}))
    any_paid = _not_admin(await db.payment_transactions.distinct("workspace_id", {"payment_status": "paid"}))
    total_workspaces_ex_admin = await db.workspaces.count_documents({"id": {"$nin": list(admin_ws)}}) if admin_ws else await db.workspaces.count_documents({})
    free_to_paid_rate = (len(any_paid) / total_workspaces_ex_admin * 100) if total_workspaces_ex_admin else 0.0
    ladder_pro_to_business = len(pro_workspaces & business_workspaces)

    total_collections = await db.collections.count_documents({})
    total_testimonials = await db.testimonials.count_documents({})
    testimonials_this_month = await db.testimonials.count_documents({"submitted_at": {"$gte": month_iso}})

    return {
        "signups": {"total": total_signups, "this_month": signups_this_month, "admin_email": admin_email or None},
        "payments": {"paid": total_paid, "pending_or_failed": failed_or_pending},
        "revenue": {
            "all_time": round(revenue_all_time, 2),
            "this_month": round(revenue_this_month, 2),
            "by_currency": {k: round(v, 2) for k, v in revenue_by_currency.items()},
        },
        "plans": plan_counts,
        "conversions": {
            "pro": len(pro_workspaces),
            "business": len(business_workspaces),
            "any_paid": len(any_paid),
            "free_to_paid_rate": round(free_to_paid_rate, 2),
            "pro_to_business": ladder_pro_to_business,
            "excludes_admin": bool(admin_ws),
            "counted_workspaces": total_workspaces_ex_admin,
        },
        "content": {
            "collections": total_collections,
            "testimonials_total": total_testimonials,
            "testimonials_this_month": testimonials_this_month,
        },
    }


# ---------- users ----------
@router.get("/users")
async def list_users(request: Request, limit: int = 500):
    from server import require_admin
    await require_admin(request)
    limit = max(1, min(limit, 2000))
    owner_ws = {}
    async for w in db.workspaces.find({}, {"_id": 0, "id": 1, "owner_id": 1, "plan": 1, "name": 1}):
        owner_ws.setdefault(w["owner_id"], []).append(w)
    users = []
    async for u in db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(limit):
        ws_list = owner_ws.get(u["id"], [])
        primary_plan = "free"
        for w in ws_list:
            if w.get("plan") in ("pro", "business"):
                primary_plan = w["plan"]; break
        users.append({
            "id": u["id"],
            "email": u.get("email"),
            "name": u.get("name"),
            "auth_provider": u.get("auth_provider"),
            "created_at": u.get("created_at"),
            "onboarded": u.get("onboarded", False),
            "workspace_count": len(ws_list),
            "plan": primary_plan,
        })
    return {"users": users, "count": len(users)}


# ---------- payments ----------
@router.get("/payments")
async def list_payments(request: Request, limit: int = 500, status: str | None = None):
    from server import require_admin
    await require_admin(request)
    limit = max(1, min(limit, 2000))
    q = {}
    if status:
        if status not in ("paid", "pending", "failed"):
            raise HTTPException(status_code=400, detail="status must be one of paid|pending|failed")
        q["payment_status"] = status
    user_map, ws_map = {}, {}
    async for u in db.users.find({}, {"_id": 0, "id": 1, "email": 1}):
        user_map[u["id"]] = u.get("email")
    async for w in db.workspaces.find({}, {"_id": 0, "id": 1, "name": 1}):
        ws_map[w["id"]] = w.get("name")
    items = []
    async for p in db.payment_transactions.find(q, {"_id": 0}).sort("created_at", -1).limit(limit):
        items.append({
            "session_id": p.get("session_id"),
            "user_id": p.get("user_id"),
            "user_email": user_map.get(p.get("user_id")),
            "workspace_id": p.get("workspace_id"),
            "workspace_name": ws_map.get(p.get("workspace_id")),
            "plan": p.get("plan"),
            "lookup_key": p.get("lookup_key"),
            "amount": (p.get("amount") or 0) / 100,
            "currency": p.get("currency"),
            "status": p.get("status"),
            "payment_status": p.get("payment_status"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
        })
    return {"payments": items, "count": len(items)}


# ---------- top collections ----------
@router.get("/collections/top")
async def top_collections(request: Request, limit: int = 20):
    from server import require_admin
    await require_admin(request)
    limit = max(1, min(limit, 200))
    ws_map = {}
    async for w in db.workspaces.find({}, {"_id": 0, "id": 1, "name": 1, "plan": 1}):
        ws_map[w["id"]] = w
    pipeline = [
        {"$group": {"_id": "$collection_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    rows = []
    async for r in db.testimonials.aggregate(pipeline):
        col = await db.collections.find_one({"id": r["_id"]}, {"_id": 0})
        if not col:
            continue
        ws = ws_map.get(col.get("workspace_id"), {})
        rows.append({
            "collection_id": col.get("id"),
            "collection_name": col.get("name"),
            "slug": col.get("slug"),
            "workspace_name": ws.get("name"),
            "workspace_plan": ws.get("plan") or "free",
            "testimonial_count": r["count"],
        })
    return {"collections": rows}


# ---------- notifications / digest ----------
@router.get("/notifications/status")
async def notifications_status(request: Request):
    from server import require_admin
    await require_admin(request)
    return await notif.queue_stats()


@router.post("/notifications/send-digest")
async def notifications_send_digest(request: Request):
    from server import require_admin
    await require_admin(request)
    return await notif.send_digest_now()
