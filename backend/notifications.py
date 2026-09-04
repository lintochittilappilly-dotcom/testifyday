"""Admin notification helpers — signup + payment-failed emails.

Modes (via `admin_notify_mode` setting):
- "instant" (default): send an email immediately, fire-and-forget.
- "daily": buffer events in `admin_notify_queue`; a background loop sends a single
  digest every 24 h.
- "off": events are still buffered (so the digest endpoint stays useful for manual
  export) but no email ever leaves.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import db
from email_service import send_email, admin_new_signup_email, admin_payment_failed_email
from settings_store import get_setting

logger = logging.getLogger("testify.notifications")

DIGEST_INTERVAL = timedelta(hours=24)
_SETTINGS_KEY_LAST_SENT = "last_digest_sent_at"


def _admin_email() -> str:
    return (os.environ.get("ADMIN_EMAIL") or "").lower().strip()


def _dashboard_url() -> str:
    origin = (os.environ.get("FRONTEND_URL") or "").rstrip("/")
    return f"{origin}/dashboard/settings" if origin else "/dashboard/settings"


async def _current_mode() -> str:
    mode = (await get_setting("admin_notify_mode") or "instant").strip().lower()
    return mode if mode in ("instant", "daily", "off") else "instant"


# ---------- enqueue + delivery ----------
async def _enqueue(event_type: str, payload: dict):
    await db.admin_notify_queue.insert_one({
        "event_type": event_type,
        "payload": payload,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sent_at": None,
    })


async def _send_signup_email(payload: dict):
    admin = _admin_email()
    if not admin:
        return
    html = admin_new_signup_email(
        payload.get("name") or "New user",
        payload.get("email") or "unknown",
        payload.get("provider") or "email",
        _dashboard_url(),
    )
    await send_email(admin, "New signup on Testify", html)


async def _send_payment_failed_email(payload: dict):
    admin = _admin_email()
    if not admin:
        return
    amount_str = f"{(payload.get('amount_cents') or 0)/100:.2f} {(payload.get('currency') or 'usd').upper()}"
    html = admin_payment_failed_email(
        payload.get("user_email") or "unknown",
        payload.get("plan") or "unknown",
        amount_str,
        payload.get("reason") or "unknown",
        _dashboard_url(),
    )
    await send_email(admin, "Payment failed on Testify", html)


# ---------- public API used by server.py ----------
def notify_admin_signup(user: dict):
    """Fire-and-forget. Skips the admin's own signup and self-sends."""
    admin = _admin_email()
    if not admin or (user.get("email") or "").lower() == admin:
        return
    payload = {
        "name": user.get("name"),
        "email": user.get("email"),
        "provider": user.get("auth_provider") or "email",
    }
    asyncio.create_task(_handle_event("signup", payload))


def notify_admin_payment_failed(user_email: Optional[str], plan: str, amount_cents: int, currency: str, reason: str):
    """Fire-and-forget."""
    if not _admin_email():
        return
    payload = {
        "user_email": user_email,
        "plan": plan or "unknown",
        "amount_cents": amount_cents or 0,
        "currency": currency or "usd",
        "reason": reason or "Payment failed",
    }
    asyncio.create_task(_handle_event("payment_failed", payload))


async def _handle_event(event_type: str, payload: dict):
    try:
        mode = await _current_mode()
        if mode == "off":
            await _enqueue(event_type, payload)  # still logged
            return
        if mode == "daily":
            await _enqueue(event_type, payload)
            return
        # instant
        await _enqueue(event_type, payload)  # keep a record of every event
        if event_type == "signup":
            await _send_signup_email(payload)
        elif event_type == "payment_failed":
            await _send_payment_failed_email(payload)
    except Exception as e:
        logger.warning(f"Notify handling failed for {event_type}: {e}")


# ---------- digest ----------
def _digest_html(signups: list, payment_failures: list) -> str:
    def rows(items, cols):
        if not items:
            return "<p style='color:#888'>None.</p>"
        head = "".join(f"<th style='text-align:left;padding:6px 8px;border-bottom:1px solid #262626'>{c}</th>" for c, _ in cols)
        body = "".join(
            "<tr>" + "".join(f"<td style='padding:6px 8px;border-bottom:1px solid #1a1a1a'>{fn(x)}</td>" for _, fn in cols) + "</tr>"
            for x in items
        )
        return f"<table style='width:100%;font-size:13px;border-collapse:collapse'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    signup_table = rows(signups, [
        ("When", lambda x: x.get("created_at", "")[:19].replace("T", " ")),
        ("Name", lambda x: x["payload"].get("name") or "—"),
        ("Email", lambda x: x["payload"].get("email") or "—"),
        ("Provider", lambda x: x["payload"].get("provider") or "email"),
    ])
    fail_table = rows(payment_failures, [
        ("When", lambda x: x.get("created_at", "")[:19].replace("T", " ")),
        ("Customer", lambda x: x["payload"].get("user_email") or "—"),
        ("Plan", lambda x: x["payload"].get("plan") or "—"),
        ("Amount", lambda x: f"{(x['payload'].get('amount_cents') or 0)/100:.2f} {(x['payload'].get('currency') or 'usd').upper()}"),
        ("Reason", lambda x: x["payload"].get("reason") or "—"),
    ])
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;background:#0a0a0a;color:#fafafa;border-radius:16px">
      <h1 style="font-size:22px;margin:0 0 8px">Testify — daily digest</h1>
      <p style="color:#a3a3a3;margin:0 0 20px">{len(signups)} new signup(s) · {len(payment_failures)} payment failure(s) in the last 24 hours.</p>
      <h2 style="font-size:16px;margin:16px 0 6px">Signups</h2>
      {signup_table}
      <h2 style="font-size:16px;margin:20px 0 6px">Failed payments</h2>
      {fail_table}
    </div>
    """


async def send_digest_now() -> dict:
    """Aggregate all unsent events and send one email. Returns a small summary."""
    admin = _admin_email()
    unsent = await db.admin_notify_queue.find({"sent_at": None}).sort("created_at", 1).to_list(2000)
    signups = [e for e in unsent if e["event_type"] == "signup"]
    fails = [e for e in unsent if e["event_type"] == "payment_failed"]
    result = {"signups": len(signups), "payment_failures": len(fails), "sent": False, "reason": None}

    if not unsent:
        result["reason"] = "No new events to report."
    elif not admin:
        result["reason"] = "ADMIN_EMAIL is not configured."
    else:
        try:
            html = _digest_html(signups, fails)
            await send_email(admin, f"Testify digest — {len(signups)} signup(s), {len(fails)} failure(s)", html)
            result["sent"] = True
        except Exception as e:
            result["reason"] = f"Delivery failed: {e}"
            logger.error(f"Digest delivery failed: {e}")

    # Mark all as sent even when there's no admin email — otherwise the queue grows forever.
    now = datetime.now(timezone.utc).isoformat()
    ids = [e["_id"] for e in unsent]
    if ids:
        await db.admin_notify_queue.update_many({"_id": {"$in": ids}}, {"$set": {"sent_at": now}})
    await db.platform_settings.update_one(
        {"id": "global"}, {"$set": {_SETTINGS_KEY_LAST_SENT: now}}, upsert=True
    )
    return result


async def get_last_sent() -> Optional[str]:
    doc = await db.platform_settings.find_one({"id": "global"}, {"_id": 0, _SETTINGS_KEY_LAST_SENT: 1}) or {}
    return doc.get(_SETTINGS_KEY_LAST_SENT)


async def queue_stats() -> dict:
    pending = await db.admin_notify_queue.count_documents({"sent_at": None})
    pending_signups = await db.admin_notify_queue.count_documents({"sent_at": None, "event_type": "signup"})
    pending_fails = await db.admin_notify_queue.count_documents({"sent_at": None, "event_type": "payment_failed"})
    last_sent = await get_last_sent()
    return {
        "pending_total": pending,
        "pending_signups": pending_signups,
        "pending_payment_failures": pending_fails,
        "last_sent": last_sent,
        "mode": await _current_mode(),
    }


async def _digest_scheduler_loop():
    """Sleep-and-send loop. Runs forever; safe to run alongside a manual send button."""
    # small startup delay so it doesn't fight the first request
    await asyncio.sleep(60)
    while True:
        try:
            mode = await _current_mode()
            if mode == "daily":
                last = await get_last_sent()
                due = True
                if last:
                    try:
                        last_dt = datetime.fromisoformat(last)
                        due = (datetime.now(timezone.utc) - last_dt) >= DIGEST_INTERVAL
                    except Exception:
                        due = True
                if due:
                    await send_digest_now()
        except Exception as e:
            logger.warning(f"Digest scheduler tick failed: {e}")
        # check hourly
        await asyncio.sleep(3600)


def start_digest_scheduler():
    """Kick off the background loop. Safe to call multiple times — the second
    call is a no-op because we stash the task on the module."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_digest_scheduler_loop())


_scheduler_task: Optional[asyncio.Task] = None
