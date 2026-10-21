"""Outbound integrations: webhooks (Zapier-compatible) and review-request emails.

Both run through one background worker so nothing blocks the public submit path.
Webhook deliveries are signed with HMAC-SHA256 over `f"{timestamp}.{body}"`, the
format every webhook receiver (including Zapier's Catch Hook and standard
Stripe-style verifiers) can check.

Design notes:
* Every delivery is persisted before it is attempted, so a restart loses nothing.
* Retries use exponential backoff (1m, 2m, 4m, 8m) and give up after 5 attempts.
* Request-email campaigns are claimed per-campaign, then sent recipient by
  recipient, so a crash mid-campaign resumes where it stopped.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

import requests

from db import db
from email_service import send_email, request_testimonial_email

logger = logging.getLogger("testify.integrations")

WEBHOOK_EVENTS = (
    "testimonial.submitted",
    "testimonial.approved",
    "testimonial.updated",
    "request_email.sent",
)

MAX_ATTEMPTS = 5
RETRY_BASE_SECONDS = 60
EMAIL_BATCH = 25

# Recipients a workspace may email per rolling 30 days, by plan.
PLAN_RECIPIENT_LIMITS = {"free": 25, "pro": 1000, "business": 10000}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_worker_task = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_in(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def new_webhook_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(24)}"


def sign_payload(secret: str, timestamp: str, body: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), f"{timestamp}.{body}".encode("utf-8"), hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify_signature(secret: str, timestamp: str, body: str, signature: str) -> bool:
    return hmac.compare_digest(sign_payload(secret, timestamp, body), signature or "")


# --------------------------------------------------------------------------
# Webhooks
# --------------------------------------------------------------------------
async def emit(workspace_id: str, event: str, data: dict) -> int:
    """Queue a signed delivery to every endpoint subscribed to `event`."""
    if event not in WEBHOOK_EVENTS:
        logger.warning(f"Unknown webhook event {event}")
        return 0
    endpoints = await db.webhook_endpoints.find(
        {"workspace_id": workspace_id, "active": True, "$or": [{"events": event}, {"events": "*"}]},
        {"_id": 0, "id": 1},
    ).to_list(50)
    if not endpoints:
        return 0
    docs = [
        {
            "id": f"whd_{secrets.token_hex(8)}",
            "endpoint_id": ep["id"],
            "workspace_id": workspace_id,
            "event": event,
            "payload": data,
            "status": "pending",
            "attempts": 0,
            "next_attempt_at": _now(),
            "response_status": None,
            "response_body": None,
            "error": None,
            "created_at": _now(),
            "delivered_at": None,
        }
        for ep in endpoints
    ]
    await db.webhook_deliveries.insert_many(docs)
    return len(docs)


async def deliver(delivery_id: str) -> dict:
    """Attempt one delivery. Returns the updated delivery document."""
    delivery = await db.webhook_deliveries.find_one({"id": delivery_id}, {"_id": 0})
    if not delivery:
        return {"error": "not found"}
    endpoint = await db.webhook_endpoints.find_one({"id": delivery["endpoint_id"]}, {"_id": 0})
    if not endpoint or not endpoint.get("active"):
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {"$set": {"status": "skipped", "error": "endpoint missing or inactive"}},
        )
        return await db.webhook_deliveries.find_one({"id": delivery_id}, {"_id": 0})

    body = json.dumps(
        {
            "id": delivery["id"],
            "event": delivery["event"],
            "created_at": delivery["created_at"],
            "data": delivery["payload"],
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Testify-Webhooks/1.0",
        "X-Testify-Event": delivery["event"],
        "X-Testify-Delivery": delivery["id"],
        "X-Testify-Attempt": str(int(delivery.get("attempts", 0)) + 1),
        "X-Testify-Timestamp": timestamp,
        "X-Testify-Signature": sign_payload(endpoint["secret"], timestamp, body),
    }

    attempts = int(delivery.get("attempts", 0)) + 1
    status_code, response_body, error = None, None, None
    try:
        resp = await asyncio.to_thread(
            requests.post, endpoint["url"], data=body.encode("utf-8"), headers=headers, timeout=10
        )
        status_code = resp.status_code
        response_body = (resp.text or "")[:500]
        ok = 200 <= resp.status_code < 300
    except Exception as exc:  # network, DNS, TLS, timeout
        ok = False
        error = str(exc)[:500]

    update = {
        "attempts": attempts,
        "response_status": status_code,
        "response_body": response_body,
        "error": error,
        "last_attempt_at": _now(),
    }
    if ok:
        update["status"] = "delivered"
        update["delivered_at"] = _now()
        update["next_attempt_at"] = None
    elif attempts >= MAX_ATTEMPTS:
        update["status"] = "failed"
        update["next_attempt_at"] = None
    else:
        update["status"] = "retrying"
        update["next_attempt_at"] = _iso_in(RETRY_BASE_SECONDS * (2 ** (attempts - 1)))

    await db.webhook_deliveries.update_one({"id": delivery_id}, {"$set": update})
    return await db.webhook_deliveries.find_one({"id": delivery_id}, {"_id": 0})


async def process_due_deliveries(limit: int = 20) -> int:
    due = await db.webhook_deliveries.find(
        {"status": {"$in": ["pending", "retrying"]}, "next_attempt_at": {"$lte": _now()}},
        {"_id": 0, "id": 1},
    ).sort("next_attempt_at", 1).to_list(limit)
    for row in due:
        try:
            await deliver(row["id"])
        except Exception as exc:
            logger.warning(f"Webhook delivery {row['id']} crashed: {exc}")
    return len(due)


async def list_deliveries(workspace_id: str, endpoint_id: str | None = None, limit: int = 20) -> list:
    query = {"workspace_id": workspace_id}
    if endpoint_id:
        query["endpoint_id"] = endpoint_id
    return await db.webhook_deliveries.find(query, {"_id": 0, "payload": 0}).sort("created_at", -1).to_list(limit)


# --------------------------------------------------------------------------
# Review-request emails
# --------------------------------------------------------------------------
def normalize_emails(raw) -> tuple[list[str], list[str]]:
    """Return (valid unique lowercase emails, rejected values)."""
    if isinstance(raw, str):
        raw = re.split(r"[\s,;]+", raw)
    valid, rejected, seen = [], [], set()
    for value in raw or []:
        email = (value or "").strip().lower()
        if not email:
            continue
        if not EMAIL_RE.match(email):
            rejected.append(email[:120])
            continue
        if email in seen:
            continue
        seen.add(email)
        valid.append(email)
    return valid, rejected


async def recipient_usage(workspace_id: str, days: int = 30) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"workspace_id": workspace_id, "created_at": {"$gte": cutoff}}},
        {"$unwind": "$recipients"},
        {"$match": {"recipients.status": "sent"}},
        {"$count": "sent"},
    ]
    rows = await db.request_campaigns.aggregate(pipeline).to_list(1)
    return int(rows[0]["sent"]) if rows else 0


async def process_email_queue(limit: int = 1) -> int:
    """Send queued request emails for up to `limit` campaigns.

    Each campaign is claimed atomically so a second worker cannot send the same
    batch twice.
    """
    sent_total = 0
    for _ in range(limit):
        campaign = await db.request_campaigns.find_one_and_update(
            {"status": "queued"},
            {"$set": {"status": "sending", "started_at": _now()}},
            projection={"_id": 0},
            sort=[("created_at", 1)],
        )
        if not campaign:
            break
        sent_total += await _send_campaign(campaign)
    return sent_total


async def _send_campaign(campaign: dict) -> int:
    workspace = await db.workspaces.find_one({"id": campaign["workspace_id"]}, {"_id": 0}) or {}
    collection = await db.collections.find_one({"id": campaign["collection_id"]}, {"_id": 0}) or {}
    app_origin = (os.environ.get("CORS_ORIGINS", "").split(",")[0] or "").strip()
    link = f"{app_origin}/t/{collection.get('slug', '')}" if app_origin else f"/t/{collection.get('slug', '')}"

    sent = 0
    recipients = campaign.get("recipients", [])
    for index, recipient in enumerate(recipients):
        if recipient.get("status") != "queued":
            continue
        subject = campaign.get("subject") or f"Quick favour — would you leave {workspace.get('name', 'us')} a testimonial?"
        html = request_testimonial_email(
            workspace.get("name") or "us",
            campaign.get("message") or "",
            link,
            recipient.get("name") or "",
        )
        try:
            result = await send_email(recipient["email"], subject, html)
            ok = result.get("status") in ("success", "mock")
            error = None if ok else result.get("message")
        except Exception as exc:
            ok, error = False, str(exc)[:300]
        await db.request_campaigns.update_one(
            {"id": campaign["id"]},
            {
                "$set": {
                    f"recipients.{index}.status": "sent" if ok else "failed",
                    f"recipients.{index}.sent_at": _now() if ok else None,
                    f"recipients.{index}.error": error,
                }
            },
        )
        sent += 1 if ok else 0

    counts = await db.request_campaigns.aggregate(
        [
            {"$match": {"id": campaign["id"]}},
            {"$unwind": "$recipients"},
            {"$group": {"_id": "$recipients.status", "n": {"$sum": 1}}},
        ]
    ).to_list(10)
    by_status = {row["_id"]: row["n"] for row in counts}
    await db.request_campaigns.update_one(
        {"id": campaign["id"]},
        {
            "$set": {
                "status": "completed",
                "completed_at": _now(),
                "sent_count": by_status.get("sent", 0),
                "failed_count": by_status.get("failed", 0),
            }
        },
    )
    try:
        await emit(
            campaign["workspace_id"],
            "request_email.sent",
            {
                "campaign_id": campaign["id"],
                "collection_id": campaign["collection_id"],
                "sent": by_status.get("sent", 0),
                "failed": by_status.get("failed", 0),
            },
        )
    except Exception as exc:
        logger.warning(f"request_email.sent webhook failed: {exc}")
    return sent


# --------------------------------------------------------------------------
# Worker
# --------------------------------------------------------------------------
async def _worker_loop():
    await asyncio.sleep(5)
    while True:
        try:
            await process_due_deliveries()
            await process_email_queue()
        except Exception as exc:
            logger.warning(f"Integrations worker tick failed: {exc}")
        await asyncio.sleep(5)


def start_worker():
    """Start the delivery loop once per process."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())
