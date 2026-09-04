import os
import re
import time
import uuid
import logging
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, UploadFile, File, Response
from fastapi.responses import PlainTextResponse
from starlette.middleware.cors import CORSMiddleware

from db import db, ensure_indexes
import models as m
import auth as authlib
from storage import init_storage, put_object, get_object, APP_NAME
from email_service import (
    send_email,
    new_testimonial_email,
    welcome_submission_email,
    password_reset_email,
    team_invite_email,
    trial_ending_email,
)
import notifications as notif
from routes.admin_analytics import router as admin_analytics_router
from captcha import verify_recaptcha
from settings_store import get_settings, get_setting, update_settings, get_plans, get_video_limits
import stripe
import requests

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

PLAN_BY_LOOKUP = {"pro_monthly": "pro", "pro_yearly": "pro", "business_monthly": "business", "business_yearly": "business"}


def _is_unlimited(plan):
    return plan in ("pro", "business")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("testify")

app = FastAPI()
api = APIRouter(prefix="/api")

# ---------- helpers ----------
_rate_store = defaultdict(list)


def rate_limit(key: str, max_calls: int, window: int):
    now = time.time()
    _rate_store[key] = [t for t in _rate_store[key] if now - t < window]
    if len(_rate_store[key]) >= max_calls:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
    _rate_store[key].append(now)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or uuid.uuid4().hex[:8]


async def unique_slug(collection, base: str, exclude_id=None) -> str:
    slug = slugify(base)
    candidate = slug
    i = 1
    while True:
        q = {"slug": candidate}
        existing = await collection.find_one(q, {"_id": 0, "id": 1})
        if not existing or existing.get("id") == exclude_id:
            return candidate
        i += 1
        candidate = f"{slug}-{i}"


def public_user(u: dict) -> dict:
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").lower().strip()
    base = {k: u.get(k) for k in ["id", "name", "email", "avatar", "role", "auth_provider", "created_at"]}
    base["is_admin"] = bool(admin_email) and (u.get("email") or "").lower() == admin_email
    base["onboarded"] = u.get("onboarded", False)
    return base


async def require_admin(request: Request) -> dict:
    user = await authlib.get_current_user(request)
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").lower().strip()
    if not admin_email or (user.get("email") or "").lower() != admin_email:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _notify_admin_signup(user: dict):
    notif.notify_admin_signup(user)


async def _notify_admin_payment_failed(user_email: str, plan: str, amount_cents: int, currency: str, reason: str):
    notif.notify_admin_payment_failed(user_email, plan, amount_cents, currency, reason)


async def _accept_pending_invites(user: dict):
    """Turn any pending team invites for this user's email into memberships."""
    invites = await db.invites.find({"email": user["email"].lower(), "status": "pending"}).to_list(50)
    for inv in invites:
        exists = await db.workspace_members.find_one({"workspace_id": inv["workspace_id"], "user_id": user["id"]})
        if not exists:
            await db.workspace_members.insert_one({
                "id": m.gen_id("wm_"), "workspace_id": inv["workspace_id"], "user_id": user["id"],
                "role": inv.get("role", "member"), "created_at": m.now_iso(),
            })
        await db.invites.update_one({"id": inv["id"]}, {"$set": {"status": "accepted"}})


# ---------- Auth ----------
@api.post("/auth/register")
async def register(data: m.RegisterInput):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    uid = m.gen_id("user_")
    user = {
        "id": uid,
        "name": data.name,
        "email": email,
        "password_hash": authlib.hash_password(data.password),
        "avatar": None,
        "auth_provider": "email",
        "role": "owner",
        "email_verified": False,
        "onboarded": False,
        "created_at": m.now_iso(),
        "updated_at": m.now_iso(),
    }
    await db.users.insert_one(user)
    await _create_default_workspace(uid, data.name)
    await _accept_pending_invites(user)
    await _notify_admin_signup(user)
    token = authlib.create_access_token(uid, email)
    return {"token": token, "user": public_user(user)}


@api.post("/auth/login")
async def login(data: m.LoginInput, request: Request):
    email = data.email.lower()
    ident = f"{request.client.host}:{email}"
    await authlib.check_lockout(ident)
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not authlib.verify_password(data.password, user["password_hash"]):
        await authlib.record_failed_login(ident)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await authlib.clear_login_attempts(ident)
    await _accept_pending_invites(user)
    token = authlib.create_access_token(user["id"], email)
    return {"token": token, "user": public_user(user)}


@api.post("/auth/google")
async def google_auth(data: m.GoogleSessionInput):
    info = authlib.verify_google_id_token(data.credential)
    email = info["email"].lower()
    user = await db.users.find_one({"email": email})
    if not user:
        uid = m.gen_id("user_")
        user = {
            "id": uid,
            "name": info.get("name", email.split("@")[0]),
            "email": email,
            "password_hash": None,
            "avatar": info.get("picture"),
            "auth_provider": "google",
            "role": "owner",
            "email_verified": True,
            "onboarded": False,
            "created_at": m.now_iso(),
            "updated_at": m.now_iso(),
        }
        await db.users.insert_one(user)
        await _create_default_workspace(uid, user["name"])
        await _notify_admin_signup(user)
    else:
        await db.users.update_one({"id": user["id"]}, {"$set": {"avatar": info.get("picture") or user.get("avatar")}})
    await _accept_pending_invites(user)
    token = authlib.create_access_token(user["id"], email)
    return {"token": token, "user": public_user(user)}


@api.post("/auth/logout")
async def logout():
    return {"ok": True}


@api.get("/auth/me")
async def me(request: Request):
    user = await authlib.get_current_user(request)
    return public_user(user) | {"onboarded": user.get("onboarded", False)}


@api.put("/auth/profile")
async def update_profile(data: m.ProfileUpdate, request: Request):
    user = await authlib.get_current_user(request)
    upd = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    upd["updated_at"] = m.now_iso()
    await db.users.update_one({"id": user["id"]}, {"$set": upd})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return public_user(fresh)


@api.post("/auth/forgot-password")
async def forgot_password(data: m.ForgotPasswordInput):
    user = await db.users.find_one({"email": data.email.lower()})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["id"],
            "used": False,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        })
        reset_url = f"{os.environ.get('CORS_ORIGINS','').split(',')[0]}/reset-password?token={token}"
        await send_email(user["email"], "Reset your Testify password", password_reset_email(reset_url))
        logger.info(f"Password reset link for {user['email']}: /reset-password?token={token}")
    return {"ok": True, "message": "If an account exists, a reset link has been sent."}


@api.post("/auth/reset-password")
async def reset_password(data: m.ResetPasswordInput):
    rec = await db.password_reset_tokens.find_one({"token": data.token})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    exp = rec["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link has expired")
    await db.users.update_one({"id": rec["user_id"]}, {"$set": {"password_hash": authlib.hash_password(data.password)}})
    await db.password_reset_tokens.update_one({"token": data.token}, {"$set": {"used": True}})
    return {"ok": True}


# ---------- Workspace ----------
async def _create_default_workspace(user_id: str, name: str):
    from pymongo.errors import DuplicateKeyError
    ws = {
        "id": m.gen_id("ws_"),
        "owner_id": user_id,
        "name": name,
        "slug": None,
        "logo_url": None,
        "primary_color": "#ff5722",
        "secondary_color": "#151515",
        "button_color": "#ff5722",
        "plan": "free",
        "created_at": m.now_iso(),
        "updated_at": m.now_iso(),
    }
    for attempt in range(6):
        ws["slug"] = await unique_slug(db.workspaces, name)
        try:
            await db.workspaces.insert_one(ws)
            break
        except DuplicateKeyError:
            ws["slug"] = f"{slugify(name)}-{uuid.uuid4().hex[:5]}"
            try:
                await db.workspaces.insert_one(ws)
                break
            except DuplicateKeyError:
                continue
    await db.workspace_members.insert_one({
        "id": m.gen_id("wm_"),
        "workspace_id": ws["id"],
        "user_id": user_id,
        "role": "owner",
        "created_at": m.now_iso(),
    })
    return ws


@api.get("/workspace")
async def get_workspace(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    return ws


@api.put("/workspace")
async def update_workspace(data: m.WorkspaceUpdate, request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    upd = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    upd["updated_at"] = m.now_iso()
    await db.workspaces.update_one({"id": ws["id"]}, {"$set": upd})
    return await db.workspaces.find_one({"id": ws["id"]}, {"_id": 0})


@api.post("/onboarding")
async def onboarding(data: m.OnboardingInput, request: Request):
    user = await authlib.get_current_user(request)
    ws = await db.workspaces.find_one({"owner_id": user["id"]}, {"_id": 0})
    if not ws:
        ws = await _create_default_workspace(user["id"], data.business_name)
    await db.workspaces.update_one({"id": ws["id"]}, {"$set": {
        "name": data.business_name,
        "primary_color": data.primary_color,
        "button_color": data.primary_color,
        "logo_url": data.logo_url,
        "updated_at": m.now_iso(),
    }})
    # create first collection
    slug = await unique_slug(db.collections, data.collection_name or data.business_name)
    col = _new_collection_doc(ws["id"], {
        "name": data.collection_name or "Customer Testimonials",
        "slug": slug,
        "brand_color": data.primary_color,
        "logo_url": data.logo_url,
        "published": True,
    })
    await _insert_collection_safe(col)
    await db.users.update_one({"id": user["id"]}, {"$set": {"onboarded": True}})
    col.pop("_id", None)
    return {"workspace": await db.workspaces.find_one({"id": ws["id"]}, {"_id": 0}), "collection": col}


# ---------- Collections ----------
def _new_collection_doc(workspace_id: str, data: dict) -> dict:
    base = m.CollectionInput(**data).model_dump()
    base.update({
        "id": m.gen_id("col_"),
        "workspace_id": workspace_id,
        "views": 0,
        "submissions": 0,
        "created_at": m.now_iso(),
        "updated_at": m.now_iso(),
    })
    return base


async def _insert_collection_safe(col: dict):
    from pymongo.errors import DuplicateKeyError
    for _ in range(6):
        try:
            await db.collections.insert_one(col)
            return col
        except DuplicateKeyError:
            col["slug"] = f"{slugify(col.get('name', 'page'))}-{uuid.uuid4().hex[:5]}"
    raise HTTPException(status_code=500, detail="Could not create collection")


@api.get("/collections")
async def list_collections(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    cols = await db.collections.find({"workspace_id": ws["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for c in cols:
        c["testimonial_count"] = await db.testimonials.count_documents({"collection_id": c["id"]})
    return cols


@api.post("/collections")
async def create_collection(data: m.CollectionInput, request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    if not _is_unlimited(ws.get("plan", "free")):
        if await db.collections.count_documents({"workspace_id": ws["id"]}) >= 1:
            raise HTTPException(status_code=402, detail="Free plan allows 1 collection page. Upgrade to Pro for unlimited.")
    slug = await unique_slug(db.collections, data.slug or data.name)
    doc = data.model_dump()
    doc["slug"] = slug
    col = _new_collection_doc(ws["id"], doc)
    await _insert_collection_safe(col)
    col.pop("_id", None)
    return col


async def _owned_collection(request: Request, col_id: str):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    col = await db.collections.find_one({"id": col_id, "workspace_id": ws["id"]}, {"_id": 0})
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ws, col


@api.get("/collections/{col_id}")
async def get_collection(col_id: str, request: Request):
    _, col = await _owned_collection(request, col_id)
    return col


@api.put("/collections/{col_id}")
async def update_collection(col_id: str, data: m.CollectionUpdate, request: Request):
    ws, col = await _owned_collection(request, col_id)
    upd = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if "slug" in upd:
        upd["slug"] = await unique_slug(db.collections, upd["slug"], exclude_id=col_id)
    upd["updated_at"] = m.now_iso()
    await db.collections.update_one({"id": col_id}, {"$set": upd})
    return await db.collections.find_one({"id": col_id}, {"_id": 0})


@api.delete("/collections/{col_id}")
async def delete_collection(col_id: str, request: Request):
    ws, col = await _owned_collection(request, col_id)
    await db.collections.delete_one({"id": col_id})
    return {"ok": True}


# ---------- Testimonials ----------
@api.get("/testimonials")
async def list_testimonials(request: Request, status: str = None, collection_id: str = None,
                            tag: str = None, type: str = None, featured: bool = None, search: str = None):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    q = {"workspace_id": ws["id"]}
    if status:
        q["status"] = status
    if collection_id:
        q["collection_id"] = collection_id
    if tag:
        q["tags"] = tag
    if featured is not None:
        q["featured"] = featured
    if type == "video":
        q["video_url"] = {"$ne": None}
    elif type == "text":
        q["video_url"] = None
    items = await db.testimonials.find(q, {"_id": 0}).sort("submitted_at", -1).to_list(500)
    if search:
        s = search.lower()
        items = [t for t in items if s in (t.get("text", "") or "").lower()
                 or s in (t.get("first_name", "") or "").lower()
                 or s in (t.get("last_name", "") or "").lower()
                 or s in (t.get("company", "") or "").lower()]
    return items


@api.get("/testimonials/{tid}")
async def get_testimonial(tid: str, request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    t = await db.testimonials.find_one({"id": tid, "workspace_id": ws["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return t


async def _owned_testimonial(request: Request, tid: str):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    t = await db.testimonials.find_one({"id": tid, "workspace_id": ws["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return ws, t


@api.put("/testimonials/{tid}")
async def update_testimonial(tid: str, data: m.TestimonialUpdate, request: Request):
    ws, t = await _owned_testimonial(request, tid)
    upd = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if upd.get("status") == "approved" and t.get("status") != "approved":
        upd["approved_at"] = m.now_iso()
    upd["updated_at"] = m.now_iso()
    await db.testimonials.update_one({"id": tid}, {"$set": upd})
    return await db.testimonials.find_one({"id": tid}, {"_id": 0})


@api.post("/testimonials/{tid}/status")
async def set_status(tid: str, data: m.StatusInput, request: Request):
    ws, t = await _owned_testimonial(request, tid)
    if data.status not in ["pending", "approved", "rejected", "archived"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    upd = {"status": data.status, "updated_at": m.now_iso()}
    if data.status == "approved":
        upd["approved_at"] = m.now_iso()
    await db.testimonials.update_one({"id": tid}, {"$set": upd})
    return await db.testimonials.find_one({"id": tid}, {"_id": 0})


@api.post("/testimonials/{tid}/feature")
async def toggle_feature(tid: str, request: Request):
    ws, t = await _owned_testimonial(request, tid)
    await db.testimonials.update_one({"id": tid}, {"$set": {"featured": not t.get("featured", False)}})
    return await db.testimonials.find_one({"id": tid}, {"_id": 0})


@api.post("/testimonials/{tid}/tags")
async def add_tag(tid: str, data: m.TagInput, request: Request):
    ws, t = await _owned_testimonial(request, tid)
    tags = set(t.get("tags", []))
    tags.add(data.tag)
    await db.testimonials.update_one({"id": tid}, {"$set": {"tags": list(tags)}})
    if not await db.tags.find_one({"workspace_id": ws["id"], "name": data.tag}):
        await db.tags.insert_one({"id": m.gen_id("tag_"), "workspace_id": ws["id"], "name": data.tag, "created_at": m.now_iso()})
    return await db.testimonials.find_one({"id": tid}, {"_id": 0})


@api.delete("/testimonials/{tid}/tags/{tag}")
async def remove_tag(tid: str, tag: str, request: Request):
    ws, t = await _owned_testimonial(request, tid)
    tags = [x for x in t.get("tags", []) if x != tag]
    await db.testimonials.update_one({"id": tid}, {"$set": {"tags": tags}})
    return await db.testimonials.find_one({"id": tid}, {"_id": 0})


@api.delete("/testimonials/{tid}")
async def delete_testimonial(tid: str, request: Request):
    ws, t = await _owned_testimonial(request, tid)
    await db.testimonials.delete_one({"id": tid})
    return {"ok": True}


@api.get("/tags")
async def list_tags(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    tags = await db.tags.find({"workspace_id": ws["id"]}, {"_id": 0}).to_list(200)
    return tags


@api.post("/testimonials/import")
async def import_testimonial(data: m.ManualImportInput, request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    doc = {
        "id": m.gen_id("tst_"),
        "workspace_id": ws["id"],
        "collection_id": None,
        "first_name": data.first_name.strip(),
        "last_name": (data.last_name or "").strip(),
        "email": "",
        "company": (data.company or "").strip(),
        "role": (data.role or "").strip(),
        "website": "",
        "avatar_url": data.avatar_url,
        "text": (data.text or "").strip(),
        "video_url": None,
        "video_thumbnail_url": None,
        "rating": data.rating,
        "status": "approved",
        "featured": data.featured,
        "consent": True,
        "consent_text": "Imported by workspace owner.",
        "consent_at": m.now_iso(),
        "custom_answers": {},
        "tags": ["Imported"],
        "notes": "",
        "source": data.source or "Imported",
        "submitted_at": m.now_iso(),
        "approved_at": m.now_iso(),
        "created_at": m.now_iso(),
        "updated_at": m.now_iso(),
    }
    await db.testimonials.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ---------- Admin / Platform settings ----------
@api.get("/admin/stripe-status")
async def admin_stripe_status(request: Request):
    """Diagnostic: tells the admin which Stripe lookup_keys exist and in which mode."""
    await require_admin(request)
    expected = ["pro_monthly", "pro_yearly", "business_monthly", "business_yearly"]
    empty_keys = {k: {"exists": False, "price_id": None, "amount": None, "currency": None} for k in expected}
    if not stripe.api_key:
        return {
            "configured": False,
            "mode": "unknown",
            "lookup_keys": empty_keys,
            "missing": expected,
            "action": "Set STRIPE_SECRET_KEY on the server, then run `python setup_stripe.py`.",
            "error": None,
        }
    mode = "live" if stripe.api_key.startswith("sk_live_") else ("test" if stripe.api_key.startswith("sk_test_") else "unknown")
    try:
        found = {}
        for lk in expected:
            prices = stripe.Price.list(lookup_keys=[lk], active=True, limit=1).data
            found[lk] = {
                "exists": bool(prices),
                "price_id": prices[0].id if prices else None,
                "amount": (prices[0].unit_amount / 100) if prices else None,
                "currency": prices[0].currency if prices else None,
            }
        missing = [k for k, v in found.items() if not v["exists"]]
        return {
            "configured": True,
            "mode": mode,
            "lookup_keys": found,
            "missing": missing,
            "action": "All good." if not missing else "Run `python setup_stripe.py` locally with the same STRIPE_SECRET_KEY to create the missing products/prices.",
            "error": None,
        }
    except stripe.error.AuthenticationError as e:
        return {"configured": True, "mode": mode, "lookup_keys": empty_keys, "missing": expected, "action": "Fix STRIPE_SECRET_KEY.", "error": f"Stripe authentication failed: {e}"}
    except Exception as e:
        return {"configured": True, "mode": mode, "lookup_keys": empty_keys, "missing": expected, "action": "Retry after fixing the Stripe error.", "error": str(e)}


@api.get("/admin/settings")
async def admin_get_settings(request: Request):
    await require_admin(request)
    s = await get_settings()
    return {**s, "google_places_configured": bool(s.get("google_places_api_key"))}


@api.put("/admin/settings")
async def admin_update_settings(data: m.SettingsInput, request: Request):
    await require_admin(request)
    payload = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    return await update_settings(payload)


@api.post("/testimonials/import-google")
async def import_google_reviews(data: m.GoogleImportInput, request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    key = await get_setting("google_places_api_key")
    if not key:
        raise HTTPException(status_code=400, detail="Google Places API key not configured. Ask your admin to add it in Settings → Integrations.")
    query = data.query.strip()
    place_id = query
    # Resolve a place_id if the input is not already one
    if not query.startswith("ChIJ"):
        try:
            find = requests.get(
                "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
                params={"input": query, "inputtype": "textquery", "fields": "place_id", "key": key},
                timeout=15,
            ).json()
            candidates = find.get("candidates", [])
            if not candidates:
                raise HTTPException(status_code=404, detail="No Google business found for that name/URL. Try the exact business name.")
            place_id = candidates[0]["place_id"]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Google find place error: {e}")
            raise HTTPException(status_code=502, detail="Could not reach Google Places. Check the API key.")
    try:
        details = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id, "fields": "name,reviews", "key": key},
            timeout=15,
        ).json()
    except Exception as e:
        logger.error(f"Google details error: {e}")
        raise HTTPException(status_code=502, detail="Could not fetch reviews from Google.")
    if details.get("status") not in ("OK",):
        raise HTTPException(status_code=400, detail=f"Google API error: {details.get('status')} — verify the key has Places API enabled.")
    reviews = details.get("result", {}).get("reviews", []) or []
    imported = 0
    for r in reviews:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        name_parts = (r.get("author_name") or "Google User").split(" ", 1)
        doc = {
            "id": m.gen_id("tst_"), "workspace_id": ws["id"], "collection_id": None,
            "first_name": name_parts[0], "last_name": name_parts[1] if len(name_parts) > 1 else "",
            "email": "", "company": "", "role": "", "website": r.get("author_url", ""),
            "avatar_url": r.get("profile_photo_url"), "text": text, "video_url": None,
            "video_thumbnail_url": None, "rating": r.get("rating"), "status": "approved",
            "featured": False, "consent": True, "consent_text": "Imported from Google Reviews.",
            "consent_at": m.now_iso(), "custom_answers": {}, "tags": ["Imported", "Google"],
            "notes": "", "source": "Google", "submitted_at": m.now_iso(), "approved_at": m.now_iso(),
            "created_at": m.now_iso(), "updated_at": m.now_iso(),
        }
        await db.testimonials.insert_one(doc)
        imported += 1
    return {"imported": imported, "business": details.get("result", {}).get("name")}


# ---------- Widgets ----------
DEFAULT_WIDGET_CONFIG = {
    "source": "approved",  # approved | featured | tag
    "tag": None,
    "theme": "dark",
    "columns": 3,
    "limit": 9,
    "show_photo": True,
    "show_company": True,
    "show_role": True,
    "show_rating": True,
    "show_video": True,
    "accent_color": "#ff5722",
    "border_radius": 16,
    "autoplay": True,
}


@api.get("/widgets")
async def list_widgets(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    return await db.widgets.find({"workspace_id": ws["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.post("/widgets")
async def create_widget(data: m.WidgetInput, request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    if not _is_unlimited(ws.get("plan", "free")):
        if await db.widgets.count_documents({"workspace_id": ws["id"]}) >= 1:
            raise HTTPException(status_code=402, detail="Free plan allows 1 widget. Upgrade to Pro for unlimited widgets.")
    config = {**DEFAULT_WIDGET_CONFIG, **(data.configuration or {})}
    widget = {
        "id": m.gen_id("wid_"),
        "workspace_id": ws["id"],
        "name": data.name,
        "type": data.type,
        "configuration": config,
        "loads": 0,
        "created_at": m.now_iso(),
        "updated_at": m.now_iso(),
    }
    await db.widgets.insert_one(widget)
    widget.pop("_id", None)
    return widget


async def _owned_widget(request: Request, wid: str):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    w = await db.widgets.find_one({"id": wid, "workspace_id": ws["id"]}, {"_id": 0})
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    return ws, w


@api.get("/widgets/{wid}")
async def get_widget(wid: str, request: Request):
    _, w = await _owned_widget(request, wid)
    return w


@api.put("/widgets/{wid}")
async def update_widget(wid: str, data: m.WidgetUpdate, request: Request):
    ws, w = await _owned_widget(request, wid)
    upd = {}
    if data.name is not None:
        upd["name"] = data.name
    if data.type is not None:
        upd["type"] = data.type
    if data.configuration is not None:
        upd["configuration"] = {**w.get("configuration", {}), **data.configuration}
    upd["updated_at"] = m.now_iso()
    await db.widgets.update_one({"id": wid}, {"$set": upd})
    return await db.widgets.find_one({"id": wid}, {"_id": 0})


@api.delete("/widgets/{wid}")
async def delete_widget(wid: str, request: Request):
    ws, w = await _owned_widget(request, wid)
    await db.widgets.delete_one({"id": wid})
    return {"ok": True}


# ---------- Overview & Analytics ----------
@api.get("/overview")
async def overview(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    wid = ws["id"]
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    total = await db.testimonials.count_documents({"workspace_id": wid})
    approved = await db.testimonials.count_documents({"workspace_id": wid, "status": "approved"})
    pending = await db.testimonials.count_documents({"workspace_id": wid, "status": "pending"})
    video = await db.testimonials.count_documents({"workspace_id": wid, "video_url": {"$ne": None}})
    written = await db.testimonials.count_documents({"workspace_id": wid, "video_url": None})
    this_month = await db.testimonials.count_documents({"workspace_id": wid, "submitted_at": {"$gte": month_start}})
    featured = await db.testimonials.count_documents({"workspace_id": wid, "featured": True})
    views = await db.analytics_events.count_documents({"workspace_id": wid, "event_type": "collection_view"})
    widget_loads = await db.analytics_events.count_documents({"workspace_id": wid, "event_type": "widget_load"})
    recent = await db.testimonials.find({"workspace_id": wid}, {"_id": 0}).sort("submitted_at", -1).to_list(6)
    return {
        "total": total, "new": pending, "approved": approved, "video": video,
        "written": written, "this_month": this_month, "featured": featured,
        "displayed": approved, "views": views, "widget_loads": widget_loads,
        "recent": recent,
    }


@api.get("/analytics")
async def analytics(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    wid = ws["id"]
    # last 14 days submissions
    days = []
    for i in range(13, -1, -1):
        d = (datetime.now(timezone.utc) - timedelta(days=i))
        start = d.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        count = await db.testimonials.count_documents({
            "workspace_id": wid,
            "submitted_at": {"$gte": start.isoformat(), "$lt": end.isoformat()},
        })
        views = await db.analytics_events.count_documents({
            "workspace_id": wid, "event_type": "collection_view",
            "created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()},
        })
        days.append({"date": start.strftime("%b %d"), "submissions": count, "views": views})
    total_views = await db.analytics_events.count_documents({"workspace_id": wid, "event_type": "collection_view"})
    total_subs = await db.testimonials.count_documents({"workspace_id": wid})
    widget_loads = await db.analytics_events.count_documents({"workspace_id": wid, "event_type": "widget_load"})
    video = await db.testimonials.count_documents({"workspace_id": wid, "video_url": {"$ne": None}})
    written = await db.testimonials.count_documents({"workspace_id": wid, "video_url": None})
    conv = round((total_subs / total_views * 100), 1) if total_views else 0
    return {
        "timeseries": days,
        "total_views": total_views,
        "total_submissions": total_subs,
        "conversion_rate": conv,
        "widget_loads": widget_loads,
        "video": video,
        "written": written,
    }


@api.post("/analytics/event")
async def record_event(data: m.AnalyticsEventInput, request: Request):
    # public event recorder; find workspace via widget/collection
    ws_id = None
    if data.widget_id:
        w = await db.widgets.find_one({"id": data.widget_id}, {"_id": 0, "workspace_id": 1})
        ws_id = w["workspace_id"] if w else None
    elif data.collection_id:
        c = await db.collections.find_one({"id": data.collection_id}, {"_id": 0, "workspace_id": 1})
        ws_id = c["workspace_id"] if c else None
    if not ws_id:
        return {"ok": False}
    await db.analytics_events.insert_one({
        "id": m.gen_id("ev_"),
        "workspace_id": ws_id,
        "widget_id": data.widget_id,
        "collection_id": data.collection_id,
        "event_type": data.event_type,
        "metadata": data.metadata,
        "created_at": m.now_iso(),
    })
    return {"ok": True}


# ---------- Upload / Media ----------
ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "video/webm", "video/mp4", "video/quicktime", "video/ogg",
}
MAX_SIZE = 80 * 1024 * 1024  # 80MB


@api.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    rate_limit(f"upload:{request.client.host}", 30, 60)
    ct = file.content_type or "application/octet-stream"
    if ct not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    is_video = ct.startswith("video/")
    is_image = ct.startswith("image/")
    data = await file.read()
    size = len(data)
    if is_video:
        limits = await get_video_limits()
        biggest = max(int(limits.get("pro", {}).get("max_size_mb", 50)), int(limits.get("business", {}).get("max_size_mb", 200)))
        if size > biggest * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"Video is too large. Max {biggest}MB.")
    elif is_image:
        if size > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image is too large. Max 5MB.")
    else:
        if size > MAX_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_SIZE // (1024*1024)}MB.")
    ext = (file.filename or "bin").split(".")[-1].lower()
    path = f"{APP_NAME}/uploads/{uuid.uuid4().hex}.{ext}"
    try:
        result = put_object(path, data, ct)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed. Please try again.")
    await db.files.insert_one({
        "id": m.gen_id("file_"),
        "storage_path": result["path"],
        "content_type": ct,
        "size": len(data),
        "is_deleted": False,
        "created_at": m.now_iso(),
    })
    return {"url": f"/api/media/{result['path']}", "path": result["path"]}


@api.get("/media/{path:path}")
async def media(path: str):
    rec = await db.files.find_one({"storage_path": path, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="File not found")
    data, ct = get_object(path)
    return Response(content=data, media_type=rec.get("content_type", ct),
                    headers={"Cache-Control": "public, max-age=31536000"})


# ---------- Public collection ----------
async def _public_collection(col: dict, ws: dict) -> dict:
    plan = ws.get("plan", "free")
    limits = await get_video_limits()
    plan_key = "business" if plan == "business" else "pro"
    video_cfg = limits.get(plan_key, {}) if _is_unlimited(plan) else {}
    return {
        "id": col["id"], "name": col["name"], "slug": col["slug"],
        "headline": col.get("headline"), "description": col.get("description"),
        "logo_url": col.get("logo_url") or ws.get("logo_url"),
        "brand_color": col.get("brand_color"), "background_color": col.get("background_color"),
        "welcome_video_url": col.get("welcome_video_url"),
        "allow_video": col.get("allow_video", True) and _is_unlimited(plan),
        "allow_text": col.get("allow_text", True),
        "require_email": col.get("require_email", True), "require_company": col.get("require_company", False),
        "require_role": col.get("require_role", False), "collect_rating": col.get("collect_rating", True),
        "custom_questions": col.get("custom_questions", []),
        "thank_you_message": col.get("thank_you_message"), "redirect_url": col.get("redirect_url"),
        "business_name": ws.get("name"),
        "video_max_duration_sec": video_cfg.get("max_duration_sec"),
        "video_max_size_mb": video_cfg.get("max_size_mb"),
        "video_min_duration_sec": limits.get("min_duration_sec", 10) if _is_unlimited(plan) else None,
    }


@api.get("/public/collection/{slug}")
async def public_collection(slug: str):
    col = await db.collections.find_one({"slug": slug}, {"_id": 0})
    if not col or not col.get("published"):
        raise HTTPException(status_code=404, detail="Collection page not found or unpublished")
    ws = await db.workspaces.find_one({"id": col["workspace_id"]}, {"_id": 0})
    await db.collections.update_one({"id": col["id"]}, {"$inc": {"views": 1}})
    await db.analytics_events.insert_one({
        "id": m.gen_id("ev_"), "workspace_id": ws["id"], "collection_id": col["id"],
        "widget_id": None, "event_type": "collection_view", "metadata": {}, "created_at": m.now_iso(),
    })
    return await _public_collection(col, ws)


@api.post("/public/collection/{slug}/submit")
async def submit_testimonial(slug: str, data: m.TestimonialSubmit, request: Request):
    rate_limit(f"submit:{request.client.host}", 5, 300)
    if data.honeypot:
        raise HTTPException(status_code=400, detail="Spam detected")
    col = await db.collections.find_one({"slug": slug}, {"_id": 0})
    if not col or not col.get("published"):
        raise HTTPException(status_code=404, detail="Collection page not found")
    if not verify_recaptcha(data.recaptcha_token, await get_setting("recaptcha_secret_key")):
        raise HTTPException(status_code=400, detail="Captcha verification failed. Please try again.")
    if not data.text and not data.video_url and not data.image_url:
        raise HTTPException(status_code=400, detail="Please provide a written, image or video testimonial")
    if not data.consent:
        raise HTTPException(status_code=400, detail="Consent is required to submit")
    if col.get("require_email") and not (data.email or "").strip():
        raise HTTPException(status_code=400, detail="Email is required")
    if col.get("require_company") and not (data.company or "").strip():
        raise HTTPException(status_code=400, detail="Company is required")
    if col.get("require_role") and not (data.role or "").strip():
        raise HTTPException(status_code=400, detail="Job title is required")
    ws = await db.workspaces.find_one({"id": col["workspace_id"]}, {"_id": 0})
    plan = ws.get("plan", "free")
    if not _is_unlimited(plan):
        if data.video_url:
            raise HTTPException(status_code=402, detail="Video testimonials are a paid feature. This business is on the Free plan.")
        if await db.testimonials.count_documents({"workspace_id": ws["id"]}) >= 5:
            raise HTTPException(status_code=402, detail="This business has reached its Free plan limit of 5 testimonials. Please try again later.")
    elif data.video_url:
        # Paid plan video cap (0 = unlimited)
        limits = await get_video_limits()
        plan_key = "business" if plan == "business" else "pro"
        max_count = int((limits.get(plan_key) or {}).get("max_count") or 0)
        if max_count > 0:
            existing = await db.testimonials.count_documents({"workspace_id": ws["id"], "video_url": {"$ne": None}})
            if existing >= max_count:
                raise HTTPException(status_code=402, detail=f"This business has reached its plan limit of {max_count} video testimonials.")
    doc = {
        "id": m.gen_id("tst_"),
        "workspace_id": ws["id"],
        "collection_id": col["id"],
        "first_name": data.first_name.strip(),
        "last_name": (data.last_name or "").strip(),
        "email": (data.email or "").strip().lower(),
        "company": (data.company or "").strip(),
        "role": (data.role or "").strip(),
        "website": (data.website or "").strip(),
        "avatar_url": data.avatar_url,
        "text": (data.text or "").strip(),
        "image_url": data.image_url,
        "video_url": data.video_url,
        "video_thumbnail_url": data.video_thumbnail_url,
        "rating": data.rating,
        "status": "pending",
        "featured": False,
        "consent": data.consent,
        "consent_text": f"I give {ws.get('name')} permission to use this testimonial on its website and marketing materials.",
        "consent_at": m.now_iso() if data.consent else None,
        "custom_answers": data.custom_answers,
        "tags": [],
        "notes": "",
        "source": col["name"],
        "submitted_at": m.now_iso(),
        "approved_at": None,
        "created_at": m.now_iso(),
        "updated_at": m.now_iso(),
    }
    await db.testimonials.insert_one(doc)
    await db.collections.update_one({"id": col["id"]}, {"$inc": {"submissions": 1}})
    # notify owner
    owner = await db.users.find_one({"id": ws["owner_id"]}, {"_id": 0})
    if owner and owner.get("email"):
        preview = doc["text"][:140] if doc["text"] else "New video testimonial"
        app_origin = os.environ.get("CORS_ORIGINS", "").split(",")[0]
        view_url = f"{app_origin}/dashboard/testimonials/{doc['id']}"
        await send_email(owner["email"], "You received a new testimonial 🎉",
                         new_testimonial_email(f"{doc['first_name']} {doc['last_name']}".strip(), preview, bool(doc["video_url"]), view_url))
    if doc["email"]:
        await send_email(doc["email"], f"Thanks for your testimonial!", welcome_submission_email(doc["first_name"], ws.get("name")))
    return {"ok": True, "thank_you_message": col.get("thank_you_message"), "redirect_url": col.get("redirect_url")}


# ---------- Public widget ----------
def _public_testimonial(t: dict) -> dict:
    return {
        "id": t["id"], "first_name": t.get("first_name"), "last_name": t.get("last_name"),
        "company": t.get("company"), "role": t.get("role"), "avatar_url": t.get("avatar_url"),
        "text": t.get("text"), "image_url": t.get("image_url"), "video_url": t.get("video_url"),
        "video_thumbnail_url": t.get("video_thumbnail_url"), "rating": t.get("rating"),
        "featured": t.get("featured"),
    }


@api.get("/public/wall/{ws_slug}")
async def public_wall(ws_slug: str):
    ws = await db.workspaces.find_one({"slug": ws_slug}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Wall not found")
    items = await db.testimonials.find(
        {"workspace_id": ws["id"], "status": "approved"}, {"_id": 0}
    ).sort("approved_at", -1).to_list(200)
    # find a published collection slug to link the collect CTA
    col = await db.collections.find_one({"workspace_id": ws["id"], "published": True}, {"_id": 0, "slug": 1})
    return {
        "business_name": ws.get("name"),
        "logo_url": ws.get("logo_url"),
        "primary_color": ws.get("primary_color", "#ff5722"),
        "slug": ws.get("slug"),
        "collect_slug": col["slug"] if col else None,
        "testimonials": [_public_testimonial(t) for t in items],
        "count": len(items),
        "branding": ws.get("plan", "free") == "free",
    }


@api.get("/public/widget/{wid}")
async def public_widget(wid: str, request: Request):
    w = await db.widgets.find_one({"id": wid}, {"_id": 0})
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    cfg = w.get("configuration", {})
    q = {"workspace_id": w["workspace_id"], "status": "approved"}
    if cfg.get("source") == "featured":
        q["featured"] = True
    elif cfg.get("source") == "tag" and cfg.get("tag"):
        q["tags"] = cfg["tag"]
    limit = int(cfg.get("limit", 9) or 9)
    items = await db.testimonials.find(q, {"_id": 0}).sort("approved_at", -1).to_list(limit)
    ws = await db.workspaces.find_one({"id": w["workspace_id"]}, {"_id": 0})
    await db.widgets.update_one({"id": wid}, {"$inc": {"loads": 1}})
    await db.analytics_events.insert_one({
        "id": m.gen_id("ev_"), "workspace_id": w["workspace_id"], "widget_id": wid,
        "collection_id": None, "event_type": "widget_load", "metadata": {}, "created_at": m.now_iso(),
    })
    return {
        "id": w["id"], "name": w["name"], "type": w["type"], "configuration": cfg,
        "business_name": ws.get("name") if ws else "",
        "branding": (ws.get("plan", "free") if ws else "free") == "free",
        "testimonials": [_public_testimonial(t) for t in items],
    }


@api.get("/widget.js")
async def widget_js():
    js = """(function(){
  var scripts = document.querySelectorAll('script[data-widget-id]');
  scripts.forEach(function(s){
    if(s.getAttribute('data-testify-init'))return;
    s.setAttribute('data-testify-init','1');
    var id = s.getAttribute('data-widget-id');
    var origin = new URL(s.src).origin;
    var iframe = document.createElement('iframe');
    iframe.src = origin + '/embed/' + id;
    iframe.style.width='100%';iframe.style.border='0';iframe.style.overflow='hidden';
    iframe.setAttribute('scrolling','no');iframe.setAttribute('title','Testimonials');
    iframe.style.minHeight='200px';
    s.parentNode.insertBefore(iframe,s);
    window.addEventListener('message',function(e){
      if(e.data && e.data.type==='testify-resize' && e.data.widgetId===id){iframe.style.height=e.data.height+'px';}
    });
  });
})();"""
    return PlainTextResponse(js, media_type="application/javascript",
                             headers={"Cache-Control": "public, max-age=300"})


# ---------- Team members ----------
async def _require_manage(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    role = await authlib.get_ws_role(user["id"], ws["id"])
    if ws.get("owner_id") != user["id"] and role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can manage the team")
    return user, ws


@api.get("/members")
async def list_members(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    mems = await db.workspace_members.find({"workspace_id": ws["id"]}, {"_id": 0}).to_list(100)
    out = []
    for mem in mems:
        u = await db.users.find_one({"id": mem["user_id"]}, {"_id": 0, "password_hash": 0})
        if u:
            out.append({"user_id": u["id"], "name": u["name"], "email": u["email"], "avatar": u.get("avatar"),
                        "role": mem["role"], "is_owner": u["id"] == ws.get("owner_id"), "joined_at": mem.get("created_at")})
    invites = await db.invites.find({"workspace_id": ws["id"], "status": "pending"}, {"_id": 0}).to_list(100)
    my_role = await authlib.get_ws_role(user["id"], ws["id"])
    return {"members": out, "invites": [{"email": i["email"], "role": i["role"]} for i in invites],
            "can_manage": ws.get("owner_id") == user["id"] or my_role in ("owner", "admin"),
            "plan": ws.get("plan", "free")}


@api.post("/members/invite")
async def invite_member(data: m.InviteInput, request: Request):
    user, ws = await _require_manage(request)
    if ws.get("plan") != "business":
        raise HTTPException(status_code=402, detail="Team members are a Business plan feature. Upgrade to invite teammates.")
    if data.role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Invalid role")
    email = data.email.lower()
    existing_user = await db.users.find_one({"email": email})
    if existing_user:
        already = await db.workspace_members.find_one({"workspace_id": ws["id"], "user_id": existing_user["id"]})
        if already:
            raise HTTPException(status_code=400, detail="This person is already on your team")
        await db.workspace_members.insert_one({
            "id": m.gen_id("wm_"), "workspace_id": ws["id"], "user_id": existing_user["id"],
            "role": data.role, "created_at": m.now_iso(),
        })
        status = "added"
    else:
        await db.invites.update_one(
            {"workspace_id": ws["id"], "email": email},
            {"$set": {"id": m.gen_id("inv_"), "workspace_id": ws["id"], "email": email, "role": data.role,
                      "invited_by": user["name"], "status": "pending", "created_at": m.now_iso()}},
            upsert=True,
        )
        status = "invited"
    app_origin = os.environ.get("CORS_ORIGINS", "").split(",")[0]
    url = f"{app_origin}/{'login' if existing_user else 'register'}"
    await send_email(email, f"You're invited to join {ws.get('name')} on Testify",
                     team_invite_email(ws.get("name"), user["name"], data.role, url, bool(existing_user)))
    return {"status": status}


@api.delete("/members/{user_id}")
async def remove_member(user_id: str, request: Request):
    user, ws = await _require_manage(request)
    if user_id == ws.get("owner_id"):
        raise HTTPException(status_code=400, detail="The workspace owner cannot be removed")
    mem = await db.workspace_members.find_one({"workspace_id": ws["id"], "user_id": user_id})
    if not mem:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.workspace_members.delete_one({"workspace_id": ws["id"], "user_id": user_id})
    await db.users.update_one({"id": user_id, "active_workspace_id": ws["id"]}, {"$set": {"active_workspace_id": None}})
    return {"ok": True}


@api.get("/workspaces/mine")
async def my_workspaces(request: Request):
    user = await authlib.get_current_user(request)
    mems = await db.workspace_members.find({"user_id": user["id"]}, {"_id": 0}).to_list(50)
    active = (await authlib.get_user_workspace(user))["id"]
    out = []
    for mem in mems:
        ws = await db.workspaces.find_one({"id": mem["workspace_id"]}, {"_id": 0})
        if ws:
            out.append({"id": ws["id"], "name": ws["name"], "role": mem["role"],
                        "is_owner": ws.get("owner_id") == user["id"], "active": ws["id"] == active})
    return out


@api.post("/workspaces/switch")
async def switch_workspace(data: m.SwitchWorkspaceInput, request: Request):
    user = await authlib.get_current_user(request)
    mem = await db.workspace_members.find_one({"workspace_id": data.workspace_id, "user_id": user["id"]})
    if not mem:
        raise HTTPException(status_code=403, detail="You don't have access to that workspace")
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_workspace_id": data.workspace_id}})
    return {"ok": True}


# ---------- Custom domain ----------
@api.put("/workspace/domain")
async def set_domain(data: m.DomainInput, request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    if ws.get("owner_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Only the owner can manage the custom domain")
    if ws.get("plan") != "business":
        raise HTTPException(status_code=402, detail="Custom domains are a Business plan feature.")
    domain = re.sub(r"^https?://", "", data.domain.strip().lower()).strip("/")
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
        raise HTTPException(status_code=400, detail="Please enter a valid domain like reviews.yourbrand.com")
    token = "testify-verify=" + secrets.token_hex(12)
    await db.workspaces.update_one({"id": ws["id"]}, {"$set": {
        "custom_domain": domain, "domain_status": "pending", "domain_token": token, "updated_at": m.now_iso(),
    }})
    return await db.workspaces.find_one({"id": ws["id"]}, {"_id": 0})


@api.post("/workspace/domain/verify")
async def verify_domain(request: Request):
    import dns.resolver
    rate_limit(f"domverify:{request.client.host}", 10, 60)
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    if ws.get("owner_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Only the owner can verify the domain")
    domain = ws.get("custom_domain")
    token = ws.get("domain_token", "")
    if not domain:
        raise HTTPException(status_code=400, detail="No custom domain set")
    verified = False
    try:
        answers = dns.resolver.resolve(f"_testify.{domain}", "TXT", lifetime=6)
        for r in answers:
            if token.split("=")[-1] in r.to_text().strip('"'):
                verified = True
                break
    except Exception:
        verified = False
    status = "verified" if verified else "failed"
    await db.workspaces.update_one({"id": ws["id"]}, {"$set": {"domain_status": status, "updated_at": m.now_iso()}})
    return {"status": status, "domain": domain}


@api.delete("/workspace/domain")
async def remove_domain(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    if ws.get("owner_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Only the owner can manage the custom domain")
    await db.workspaces.update_one({"id": ws["id"]}, {"$unset": {"custom_domain": "", "domain_status": "", "domain_token": ""}})
    return {"ok": True}


# ---------- Payments (Stripe subscriptions) ----------
@api.get("/plans")
async def list_plans():
    return await get_plans()


@api.get("/public/config")
async def public_config():
    s = await get_settings()
    return {
        "recaptcha_site_key": s.get("recaptcha_site_key", ""),
        "promo_banner": s.get("promo_banner", ""),
        "trial_period_days": int(s.get("trial_period_days") or 0),
        "trial_requires_card": bool(s.get("trial_require_card", True)),
    }


@api.post("/payments/checkout")
async def create_checkout(data: m.CheckoutInput, request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    if data.lookup_key not in PLAN_BY_LOOKUP:
        raise HTTPException(status_code=400, detail="Invalid plan")
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured on the server. Set STRIPE_SECRET_KEY.")
    try:
        prices = stripe.Price.list(lookup_keys=[data.lookup_key], active=True, limit=1).data
    except stripe.error.AuthenticationError:
        raise HTTPException(status_code=500, detail="Stripe key is invalid. Check STRIPE_SECRET_KEY on the server.")
    if not prices:
        raise HTTPException(
            status_code=500,
            detail=f"No active Stripe price with lookup_key '{data.lookup_key}'. Ask the site admin to run `python setup_stripe.py` on the backend to create the Pro and Business products in the correct Stripe mode (live vs test).",
        )
    price = prices[0]
    origin = data.origin_url.rstrip("/")
    coupon_id = (await get_setting("checkout_coupon_id") or "").strip()
    discounts = [{"coupon": coupon_id}] if coupon_id else None

    # ---------- 7-day trial (admin-configurable, new customers only) ----------
    settings = await get_settings()
    trial_days = int(settings.get("trial_period_days") or 0)
    trial_require_card = bool(settings.get("trial_require_card", True))
    already_paid = await db.payment_transactions.count_documents({
        "workspace_id": ws["id"], "payment_status": "paid",
    })
    trial_applied = trial_days > 0 and already_paid == 0

    kwargs = dict(
        line_items=[{"price": price.id, "quantity": 1}],
        mode="subscription",
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/payment/cancel",
        metadata={"user_id": user["id"], "workspace_id": ws["id"], "lookup_key": data.lookup_key},
    )
    if trial_applied:
        kwargs["subscription_data"] = {"trial_period_days": trial_days}
        if not trial_require_card:
            kwargs["payment_method_collection"] = "if_required"
    if discounts:
        kwargs["discounts"] = discounts
    else:
        kwargs["allow_promotion_codes"] = True
    # Try 3 progressively simpler checkout configurations. Any StripeError → surface real message.
    session = None
    last_error = None
    for attempt_kwargs in (
        {**kwargs, "managed_payments": {"enabled": True}},
        {**kwargs, "automatic_tax": {"enabled": True}, "billing_address_collection": "required"},
        kwargs,
    ):
        try:
            session = stripe.checkout.Session.create(**attempt_kwargs)
            break
        except stripe.error.InvalidRequestError as e:
            last_error = e
            logger.warning(f"Checkout attempt rejected: {getattr(e, 'user_message', None) or e}")
            continue
        except stripe.error.StripeError as e:
            real = getattr(e, "user_message", None) or str(e)
            logger.error(f"Stripe error during checkout: {real}")
            await _notify_admin_payment_failed(user.get("email"), PLAN_BY_LOOKUP.get(data.lookup_key, "?"), price.unit_amount or 0, price.currency, real)
            raise HTTPException(status_code=400, detail=f"Stripe error: {real}")
    if session is None:
        real = getattr(last_error, "user_message", None) or str(last_error) if last_error else "unknown"
        logger.error(f"All checkout attempts failed. Final Stripe error: {real}")
        await _notify_admin_payment_failed(user.get("email"), PLAN_BY_LOOKUP.get(data.lookup_key, "?"), price.unit_amount or 0, price.currency, real)
        raise HTTPException(status_code=400, detail=f"Stripe rejected the checkout: {real}")
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["id"], "workspace_id": ws["id"],
        "lookup_key": data.lookup_key, "plan": PLAN_BY_LOOKUP[data.lookup_key],
        "amount": (price.unit_amount or 0), "currency": price.currency,
        "status": "initiated", "payment_status": "pending",
        "created_at": m.now_iso(), "updated_at": m.now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


async def _apply_paid(session_id: str):
    rec = await db.payment_transactions.find_one({"session_id": session_id})
    if rec and rec.get("workspace_id") and rec.get("plan"):
        await db.workspaces.update_one({"id": rec["workspace_id"]}, {"$set": {"plan": rec["plan"], "updated_at": m.now_iso()}})


@api.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if rec.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                res = await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "stripe_subscription_id": s.subscription,
                              "stripe_customer_id": s.customer,
                              "updated_at": m.now_iso()}},
                )
                if res.modified_count:
                    await _apply_paid(session_id)
                rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except stripe.error.StripeError:
            pass
    return {"session_id": rec["session_id"], "status": rec["status"],
            "payment_status": rec["payment_status"], "plan": rec.get("plan")}


@api.post("/payments/portal")
async def billing_portal(data: m.PortalInput, request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    rec = await db.payment_transactions.find_one(
        {"workspace_id": ws["id"], "payment_status": "paid", "stripe_customer_id": {"$ne": None}},
        {"_id": 0}, sort=[("updated_at", -1)],
    )
    if not rec or not rec.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="No active subscription to manage.")
    try:
        session = stripe.billing_portal.Session.create(
            customer=rec["stripe_customer_id"],
            return_url=data.origin_url.rstrip("/") + "/dashboard/settings",
        )
    except stripe.error.StripeError as e:
        logger.error(f"Billing portal error: {e}")
        raise HTTPException(status_code=500, detail="Could not open the billing portal. Please try again.")
    return {"portal_url": session.url}


@api.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        res = await db.payment_transactions.update_one(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"),
                      "stripe_subscription_id": obj.get("subscription"),
                      "stripe_customer_id": obj.get("customer"), "updated_at": m.now_iso()}},
        )
        if res.modified_count:
            await _apply_paid(obj["id"])
    elif t == "customer.subscription.deleted":
        sub_id = obj.get("id")
        rec = await db.payment_transactions.find_one({"stripe_subscription_id": sub_id})
        if rec and rec.get("workspace_id"):
            await db.workspaces.update_one({"id": rec["workspace_id"]}, {"$set": {"plan": "free", "updated_at": m.now_iso()}})
    elif t == "customer.subscription.trial_will_end":
        # Fires ~3 days before trial ends. Notify the customer.
        try:
            sub_id = obj.get("id")
            trial_end = obj.get("trial_end")
            rec = await db.payment_transactions.find_one({"stripe_subscription_id": sub_id}) if sub_id else None
            if rec:
                u = await db.users.find_one({"id": rec.get("user_id")}, {"_id": 0, "email": 1, "name": 1})
                if u and u.get("email"):
                    trial_end_str = (
                        datetime.fromtimestamp(trial_end, tz=timezone.utc).strftime("%b %d, %Y")
                        if trial_end else "in a few days"
                    )
                    origin = (os.environ.get("FRONTEND_URL") or "").rstrip("/") or ""
                    portal_url = f"{origin}/dashboard/settings" if origin else "/dashboard/settings"
                    html = trial_ending_email(u.get("name") or "there", rec.get("plan") or "pro", trial_end_str, portal_url)
                    await send_email(u["email"], "Your Testify trial ends in 3 days", html)
        except Exception as e:
            logger.warning(f"trial_will_end notify error: {e}")
    elif t == "invoice.payment_succeeded":
        # Trial converted to paid — flip payment_status so analytics reflect the sale.
        try:
            sub_id = obj.get("subscription")
            if sub_id:
                await db.payment_transactions.update_one(
                    {"stripe_subscription_id": sub_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"payment_status": "paid", "status": "completed", "updated_at": m.now_iso()}},
                )
        except Exception as e:
            logger.warning(f"invoice.payment_succeeded handler error: {e}")
    elif t in ("invoice.payment_failed", "charge.failed"):
        try:
            customer_id = obj.get("customer")
            rec = await db.payment_transactions.find_one({"stripe_customer_id": customer_id}, sort=[("updated_at", -1)]) if customer_id else None
            user_email = None
            if rec:
                u = await db.users.find_one({"id": rec.get("user_id")}, {"_id": 0, "email": 1})
                user_email = (u or {}).get("email")
            reason = obj.get("failure_message") or obj.get("last_payment_error", {}).get("message") or obj.get("status") or "Payment failed"
            amount_cents = obj.get("amount_due") or obj.get("amount") or (rec or {}).get("amount") or 0
            currency = obj.get("currency") or (rec or {}).get("currency") or "usd"
            plan = (rec or {}).get("plan") or "unknown"
            if rec:
                await db.payment_transactions.update_one(
                    {"session_id": rec["session_id"]},
                    {"$set": {"payment_status": "failed", "status": "failed",
                              "failure_reason": reason, "updated_at": m.now_iso()}},
                )
            await _notify_admin_payment_failed(user_email, plan, amount_cents, currency, reason)
        except Exception as e:
            logger.warning(f"Payment failed webhook notify error: {e}")
    return {"status": "ok"}


api.include_router(admin_analytics_router)
app.include_router(api)

_cors_origins = [o.strip() for o in (os.environ.get("CORS_ORIGINS", "*")).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=_cors_origins if _cors_origins != ["*"] else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health")
async def api_health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.warning(f"Storage init skipped: {e}")
    try:
        await authlib.seed_admin()
    except Exception as e:
        logger.error(f"Admin seed failed: {e}")
    try:
        notif.start_digest_scheduler()
        logger.info("Admin digest scheduler started")
    except Exception as e:
        logger.warning(f"Digest scheduler start failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    from db import client
    client.close()
