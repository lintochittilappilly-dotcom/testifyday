import requests
import logging

logger = logging.getLogger(__name__)
VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


def verify_recaptcha(token: str, secret: str) -> bool:
    """Returns True if valid or if reCAPTCHA is not configured (graceful fallback)."""
    secret = (secret or "").strip()
    if not secret:
        return True  # not configured, rely on honeypot + rate limiting
    if not token:
        return False
    try:
        resp = requests.post(VERIFY_URL, data={"secret": secret, "response": token}, timeout=5)
        return bool(resp.json().get("success"))
    except Exception as e:
        logger.error(f"reCAPTCHA verify error: {e}")
        return False
