"""Workspace-facing integrations: outbound webhooks and review-request emails.

Mounted on the `/api` router by `server.py` (same pattern as admin_analytics).
Both features are wired to the background worker in `integrations.py`.
"""
import asyncio
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

import auth as authlib
import integrations as integ
import models as m
from db import db

router = APIRouter(prefix="", tags=["integrations"])


# ---------- models ----------
class WebhookInput(BaseModel):
    url: str
    events: Optional[List[str]] = None
    description: Optional[str] = ""


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[List[str]] = None
    description: Optional[str] = None
    active: Optional[bool] = None


class RequestEmailsInput(BaseModel):
    collection_id: str
    emails: List[str]
    subject: Optional[str] = None
    message: Optional[str] = None


# ---------- helpers ----------
async def _ctx(request: Request):
    user = await authlib.get_current_user(request)
    ws = await authlib.get_user_workspace(user)
    return user, ws


async def _require_paid(request: Request):
    user, ws = await _ctx(request)
    if ws.get("plan") not in ("pro", "business"):
        raise HTTPException(status_code=402, detail="Webhooks are a Pro feature. Upgrade to connect Zapier or your own endpoint.")
    return user, ws


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Webhook URL must start with http:// or https://")
    # SSRF guard: never let a workspace point deliveries at the platform itself
    # or at loopback/link-local addresses.
    blocked = ("localhost", "127.", "0.0.0.0", "::1", "169.254.", "metadata.google.internal")
    lowered = url.lower()
    if any(token in lowered for token in blocked):
        raise HTTPException(status_code=400, detail="That webhook URL is not allowed")
    if len(url) > 500:
        raise HTTPException(status_code=400, detail="Webhook URL is too long")
    return url


async def _owned_endpoint(request: Request, endpoint_id: str):
    _, ws = await _require_paid(request)
    ep = await db.webhook_endpoints.find_one({"id": endpoint_id, "workspace_id": ws["id"]}, {"_id": 0})
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return ws, ep


def _clean_events(events) -> List[str]:
    if events in (None, []):
        return ["*"]
    if isinstance(events, str):
        events = [events]
    if "*" in events:
        return ["*"]
    cleaned = []
    for e in events:
        if e not in integ.WEBHOOK_EVENTS:
            raise HTTPException(status_code=400, detail=f"Unknown event: {e}")
        cleaned.append(e)
    return cleaned or ["*"]


def _public_endpoint(ep: dict) -> dict:
    """Never return the signing secret after creation."""
    out = {k: v for k, v in ep.items() if k != "secret"}
    out["has_secret"] = bool(ep.get("secret"))
    return out


# ---------- webhooks ----------
@router.get("/webhooks")
async def list_webhooks(request: Request):
    _, ws = await _require_paid(request)
    endpoints = await db.webhook_endpoints.find({"workspace_id": ws["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    deliveries = await integ.list_deliveries(ws["id"], limit=20)
    return {
        "endpoints": [_public_endpoint(e) for e in endpoints],
        "deliveries": deliveries,
        "events": list(integ.WEBHOOK_EVENTS),
    }


@router.post("/webhooks")
async def create_webhook(data: WebhookInput, request: Request):
    user, ws = await _require_paid(request)
    url = _validate_url(data.url)
    events = _clean_events(data.events)
    existing = await db.webhook_endpoints.count_documents({"workspace_id": ws["id"]})
    if existing >= 10:
        raise HTTPException(status_code=400, detail="You can have up to 10 webhook endpoints")
    endpoint = {
        "id": f"whk_{m.gen_id()[:12]}",
        "workspace_id": ws["id"],
        "url": url,
        "events": events,
        "description": (data.description or "").strip()[:200],
        "secret": integ.new_webhook_secret(),
        "active": True,
        "created_by": user["id"],
        "created_at": m.now_iso(),
    }
    # insert_one mutates its argument with `_id`; keep our response copy clean.
    await db.webhook_endpoints.insert_one(dict(endpoint))
    # The secret is shown exactly once — receivers need it to verify signatures.
    return {**_public_endpoint(endpoint), "secret": endpoint["secret"]}


@router.put("/webhooks/{endpoint_id}")
async def update_webhook(endpoint_id: str, data: WebhookUpdate, request: Request):
    ws, ep = await _owned_endpoint(request, endpoint_id)
    update = {}
    if data.url is not None:
        update["url"] = _validate_url(data.url)
    if data.events is not None:
        update["events"] = _clean_events(data.events)
    if data.description is not None:
        update["description"] = data.description.strip()[:200]
    if data.active is not None:
        update["active"] = bool(data.active)
    if update:
        update["updated_at"] = m.now_iso()
        await db.webhook_endpoints.update_one({"id": endpoint_id, "workspace_id": ws["id"]}, {"$set": update})
    ep = await db.webhook_endpoints.find_one({"id": endpoint_id}, {"_id": 0})
    return _public_endpoint(ep)


@router.delete("/webhooks/{endpoint_id}")
async def delete_webhook(endpoint_id: str, request: Request):
    ws, _ = await _owned_endpoint(request, endpoint_id)
    await db.webhook_endpoints.delete_one({"id": endpoint_id, "workspace_id": ws["id"]})
    return {"ok": True}


@router.post("/webhooks/{endpoint_id}/rotate-secret")
async def rotate_secret(endpoint_id: str, request: Request):
    ws, _ = await _owned_endpoint(request, endpoint_id)
    secret = integ.new_webhook_secret()
    await db.webhook_endpoints.update_one(
        {"id": endpoint_id, "workspace_id": ws["id"]}, {"$set": {"secret": secret, "updated_at": m.now_iso()}}
    )
    return {"secret": secret}


@router.post("/webhooks/{endpoint_id}/test")
async def test_webhook(endpoint_id: str, request: Request):
    ws, ep = await _owned_endpoint(request, endpoint_id)
    count = await integ.emit(
        ws["id"],
        "testimonial.submitted",
        {"test": True, "note": "This is a test delivery from Testify.", "workspace": ws.get("name")},
    )
    # emit() fans out to every subscribed endpoint, so deliver only ours.
    delivery = await db.webhook_deliveries.find_one(
        {"endpoint_id": ep["id"], "status": "pending"}, {"_id": 0, "id": 1}, sort=[("created_at", -1)]
    )
    if not delivery:
        return {"ok": False, "queued": count, "detail": "Endpoint is not subscribed to testimonial.submitted."}
    result = await integ.deliver(delivery["id"])
    return {
        "ok": result.get("status") == "delivered",
        "status": result.get("status"),
        "response_status": result.get("response_status"),
        "error": result.get("error"),
    }


@router.get("/webhooks/{endpoint_id}/deliveries")
async def webhook_deliveries(endpoint_id: str, request: Request):
    ws, ep = await _owned_endpoint(request, endpoint_id)
    return await integ.list_deliveries(ws["id"], endpoint_id=ep["id"], limit=50)


# ---------- review-request emails ----------
@router.get("/request-emails")
async def list_request_emails(request: Request):
    _, ws = await _ctx(request)
    campaigns = await db.request_campaigns.find(
        {"workspace_id": ws["id"]}, {"_id": 0, "recipients": 0}
    ).sort("created_at", -1).to_list(50)
    used = await integ.recipient_usage(ws["id"])
    limit = integ.PLAN_RECIPIENT_LIMITS.get(ws.get("plan", "free"), 25)
    return {"campaigns": campaigns, "usage": {"sent_30d": used, "limit_30d": limit, "plan": ws.get("plan", "free")}}


@router.get("/request-emails/{campaign_id}")
async def get_request_email(campaign_id: str, request: Request):
    _, ws = await _ctx(request)
    campaign = await db.request_campaigns.find_one(
        {"id": campaign_id, "workspace_id": ws["id"]}, {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/request-emails")
async def create_request_emails(data: RequestEmailsInput, request: Request):
    user, ws = await _ctx(request)
    collection = await db.collections.find_one(
        {"id": data.collection_id, "workspace_id": ws["id"]}, {"_id": 0}
    )
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not collection.get("published"):
        raise HTTPException(status_code=400, detail="Publish the collection page before emailing people about it")

    emails, rejected = integ.normalize_emails(data.emails)
    if not emails:
        raise HTTPException(status_code=400, detail="Add at least one valid email address")

    plan = ws.get("plan", "free")
    limit = integ.PLAN_RECIPIENT_LIMITS.get(plan, 25)
    used = await integ.recipient_usage(ws["id"])
    remaining = max(0, limit - used)
    if remaining <= 0:
        raise HTTPException(
            status_code=402,
            detail=f"Your {plan.title()} plan has sent its {limit} review requests for this month. Upgrade for more.",
        )

    skipped_over_quota = []
    if len(emails) > remaining:
        skipped_over_quota = emails[remaining:]
        emails = emails[:remaining]

    # Never re-ask someone who already left a testimonial.
    already = await db.testimonials.distinct(
        "email", {"workspace_id": ws["id"], "email": {"$in": emails}}
    )
    already = {e.lower() for e in already if e}
    skipped_dupes = [e for e in emails if e in already]
    emails = [e for e in emails if e not in already]
    if not emails:
        raise HTTPException(
            status_code=400,
            detail="Every address you added has already left a testimonial or is invalid.",
        )

    campaign = {
        "id": f"req_{m.gen_id()[:12]}",
        "workspace_id": ws["id"],
        "collection_id": collection["id"],
        "collection_slug": collection.get("slug"),
        "subject": (data.subject or "").strip()[:200] or None,
        "message": (data.message or "").strip()[:2000] or None,
        "status": "queued",
        "created_by": user["id"],
        "created_at": m.now_iso(),
        "recipients": [{"email": e, "name": "", "status": "queued", "sent_at": None, "error": None} for e in emails],
        "sent_count": 0,
        "failed_count": 0,
    }
    await db.request_campaigns.insert_one(campaign.copy())
    # Send immediately in the background; the worker also picks it up if we crash.
    asyncio.create_task(integ.process_email_queue(limit=1))

    return {
        "campaign": {k: v for k, v in campaign.items() if k != "recipients"},
        "queued": len(emails),
        "skipped": {
            "already_testimonial": skipped_dupes,
            "invalid": rejected,
            "over_quota": skipped_over_quota,
        },
    }


@router.post("/request-emails/{campaign_id}/retry")
async def retry_request_emails(campaign_id: str, request: Request):
    _, ws = await _ctx(request)
    campaign = await db.request_campaigns.find_one({"id": campaign_id, "workspace_id": ws["id"]}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    retried = 0
    for index, recipient in enumerate(campaign.get("recipients", [])):
        if recipient.get("status") == "failed":
            await db.request_campaigns.update_one(
                {"id": campaign_id},
                {"$set": {f"recipients.{index}.status": "queued", f"recipients.{index}.error": None}},
            )
            retried += 1
    if retried:
        await db.request_campaigns.update_one({"id": campaign_id}, {"$set": {"status": "queued"}})
        asyncio.create_task(integ.process_email_queue(limit=1))
    return {"ok": True, "retried": retried}
