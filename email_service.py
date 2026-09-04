import os
import asyncio
import logging
from settings_store import get_settings

logger = logging.getLogger(__name__)


async def _config():
    # Prefer env vars (Railway); fall back to admin-configured settings in DB.
    env_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    env_sender = (os.environ.get("SENDER_EMAIL") or "").strip()
    if env_key and env_sender:
        return env_key, env_sender
    s = await get_settings()
    return (
        env_key or (s.get("resend_api_key") or "").strip(),
        env_sender or (s.get("sender_email") or "onboarding@resend.dev").strip(),
    )


async def send_email(to: str, subject: str, html: str):
    key, sender = await _config()
    if not key:
        logger.info(f"[EMAIL:MOCK] To={to} Subject={subject}")
        return {"status": "mock", "message": "Email logging only (no RESEND_API_KEY configured)"}
    try:
        import resend
        resend.api_key = key
        params = {"from": sender, "to": [to], "subject": subject, "html": html}
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"status": "success", "email_id": result.get("id")}
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return {"status": "error", "message": str(e)}


def new_testimonial_email(customer_name: str, preview: str, is_video: bool, view_url: str) -> str:
    kind = "Video testimonial" if is_video else "Written testimonial"
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;background:#0a0a0a;color:#fafafa;border-radius:16px">
      <h1 style="font-size:22px;margin:0 0 8px">You received a new testimonial</h1>
      <p style="color:#a3a3a3;margin:0 0 20px">{kind} from <strong style="color:#fff">{customer_name}</strong></p>
      <div style="background:#151515;border:1px solid #262626;border-radius:12px;padding:16px;margin-bottom:20px">
        <p style="margin:0;color:#e5e5e5;font-style:italic">"{preview}"</p>
      </div>
      <a href="{view_url}" style="display:inline-block;background:#ff5722;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600">View testimonial</a>
    </div>
    """


def welcome_submission_email(customer_name: str, business: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <h1 style="font-size:22px">Thank you, {customer_name}!</h1>
      <p>Your testimonial for <strong>{business}</strong> has been submitted successfully. We really appreciate you taking the time to share your experience.</p>
    </div>
    """


def password_reset_email(reset_url: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <h1 style="font-size:22px">Reset your password</h1>
      <p>Click the button below to reset your password. This link expires in 1 hour.</p>
      <a href="{reset_url}" style="display:inline-block;background:#ff5722;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600">Reset password</a>
      <p style="color:#888;font-size:13px;margin-top:16px">If you didn't request this, you can safely ignore this email.</p>
    </div>
    """


def trial_ending_email(user_name: str, plan: str, trial_end_date: str, portal_url: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;background:#0a0a0a;color:#fafafa;border-radius:16px">
      <h1 style="font-size:22px;margin:0 0 8px">Your Testify trial ends soon</h1>
      <p style="color:#a3a3a3;margin:0 0 20px">Hi {user_name}, your free trial of <strong style="color:#fff">Testify {plan.title()}</strong> ends on <strong style="color:#fff">{trial_end_date}</strong>. Your card will be charged automatically unless you cancel before then.</p>
      <div style="background:#151515;border:1px solid #262626;border-radius:12px;padding:16px;margin-bottom:20px">
        <p style="margin:0 0 6px;font-weight:600">Keep your streak going</p>
        <p style="margin:0;color:#a3a3a3;font-size:14px">Your testimonials, widgets, and integrations stay live — nothing changes on day 8. Just checking in so there are no surprises.</p>
      </div>
      <a href="{portal_url}" style="display:inline-block;background:#ff5722;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600">Manage subscription</a>
      <p style="color:#a3a3a3;margin:20px 0 0;font-size:13px">Questions? Reply to this email — we read every message.</p>
    </div>
    """


def admin_new_signup_email(user_name: str, user_email: str, provider: str, dashboard_url: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;background:#0a0a0a;color:#fafafa;border-radius:16px">
      <h1 style="font-size:22px;margin:0 0 8px">New signup on Testify</h1>
      <p style="color:#a3a3a3;margin:0 0 20px"><strong style="color:#fff">{user_name}</strong> just created an account.</p>
      <div style="background:#151515;border:1px solid #262626;border-radius:12px;padding:16px;margin-bottom:20px">
        <p style="margin:0 0 4px"><strong>Email:</strong> {user_email}</p>
        <p style="margin:0"><strong>Provider:</strong> {provider}</p>
      </div>
      <a href="{dashboard_url}" style="display:inline-block;background:#ff5722;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600">Open admin dashboard</a>
    </div>
    """


def admin_payment_failed_email(user_email: str, plan: str, amount: str, reason: str, dashboard_url: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;background:#0a0a0a;color:#fafafa;border-radius:16px">
      <h1 style="font-size:22px;margin:0 0 8px;color:#f87171">Payment failed</h1>
      <p style="color:#a3a3a3;margin:0 0 20px">A checkout attempt failed on Testify. Consider reaching out.</p>
      <div style="background:#151515;border:1px solid #262626;border-radius:12px;padding:16px;margin-bottom:20px">
        <p style="margin:0 0 4px"><strong>Customer:</strong> {user_email}</p>
        <p style="margin:0 0 4px"><strong>Plan:</strong> {plan}</p>
        <p style="margin:0 0 4px"><strong>Amount:</strong> {amount}</p>
        <p style="margin:0;color:#f87171"><strong>Reason:</strong> {reason}</p>
      </div>
      <a href="{dashboard_url}" style="display:inline-block;background:#ff5722;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600">Open admin dashboard</a>
    </div>
    """


def team_invite_email(business: str, inviter: str, role: str, url: str, has_account: bool) -> str:
    action = "Log in to join" if has_account else "Create your free account to join"
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <h1 style="font-size:22px">You've been invited to {business}</h1>
      <p><strong>{inviter}</strong> invited you to collaborate on <strong>{business}</strong>'s testimonials as a <strong>{role}</strong>.</p>
      <a href="{url}" style="display:inline-block;background:#ff5722;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600">{action}</a>
      <p style="color:#888;font-size:13px;margin-top:16px">If you weren't expecting this, you can ignore this email.</p>
    </div>
    """
