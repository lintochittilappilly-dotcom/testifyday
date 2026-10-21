import os
import copy
from db import db

DEFAULT_PLANS = [
    {
        "id": "free", "name": "Free", "price_monthly": 0, "price_yearly": 0,
        "lookup_monthly": None, "lookup_yearly": None,
        "period_free": "forever",
        "features": [
            "Unlimited collection pages",
            "Up to 10 testimonials",
            "Written or image testimonials",
            "Unlimited widgets",
            "Testify branding",
        ],
        "cta": "Start free",
    },
    {
        "id": "pro", "name": "Pro", "price_monthly": 29, "price_yearly": 290,
        "lookup_monthly": "pro_monthly", "lookup_yearly": "pro_yearly",
        "features": [
            "Unlimited collection pages",
            "Unlimited testimonials",
            "Video, image and written testimonials",
            "Up to 100 video testimonials",
            "Custom branding",
            "Analytics",
            "Remove Testify branding",
        ],
        "cta": "Start free trial",
        "featured": True,
    },
    {
        "id": "business", "name": "Business", "price_monthly": 79, "price_yearly": 790,
        "lookup_monthly": "business_monthly", "lookup_yearly": "business_yearly",
        "features": [
            "Everything in Pro",
            "Unlimited video testimonials",
            "Team members",
            "Advanced analytics",
            "Custom domain",
            "Priority support",
            "Advanced customization",
        ],
        "cta": "Start free trial",
    },
]

SETTING_KEYS = [
    "recaptcha_site_key",
    "recaptcha_secret_key",
    "resend_api_key",
    "sender_email",
    "google_places_api_key",
    "checkout_coupon_id",
    "promo_banner",
    "plans_override",
    "video_limits",
    "homepage_wall_slug",
    "ai_captions_enabled",
    "admin_notify_mode",
    "trial_period_days",
    "trial_require_card",
]

DEFAULT_VIDEO_LIMITS = {
    "min_duration_sec": 10,
    "pro": {"max_duration_sec": 60, "max_size_mb": 50, "max_count": 100},
    "business": {"max_duration_sec": 180, "max_size_mb": 200, "max_count": 0},
}


def _env_defaults():
    return {
        "recaptcha_site_key": os.environ.get("RECAPTCHA_SITE_KEY", ""),
        "recaptcha_secret_key": os.environ.get("RECAPTCHA_SECRET_KEY", ""),
        "resend_api_key": os.environ.get("RESEND_API_KEY", ""),
        "sender_email": os.environ.get("SENDER_EMAIL", "onboarding@resend.dev"),
        "google_places_api_key": os.environ.get("GOOGLE_PLACES_API_KEY", ""),
        "checkout_coupon_id": "",
        "promo_banner": "",
    "plans_override": [],
    "video_limits": {},
    "homepage_wall_slug": "",
    # Default on when the deployment already has a provider key, so captions
    # start working without an extra admin step.
    "ai_captions_enabled": bool(os.environ.get("OPENAI_API_KEY")),
        "admin_notify_mode": "instant",
        "trial_period_days": 7,
        "trial_require_card": True,
    }


async def get_video_limits() -> dict:
    """Merge admin overrides on top of DEFAULT_VIDEO_LIMITS."""
    import copy
    limits = copy.deepcopy(DEFAULT_VIDEO_LIMITS)
    override = await get_setting("video_limits") or {}
    if isinstance(override, dict):
        if "min_duration_sec" in override:
            try:
                limits["min_duration_sec"] = int(override["min_duration_sec"])
            except Exception:
                pass
        for tier in ("pro", "business"):
            t = override.get(tier) or {}
            if isinstance(t, dict):
                for k in ("max_duration_sec", "max_size_mb", "max_count"):
                    if k in t:
                        try:
                            limits[tier][k] = int(t[k])
                        except Exception:
                            pass
    return limits


async def get_settings() -> dict:
    doc = await db.platform_settings.find_one({"id": "global"}, {"_id": 0}) or {}
    defaults = _env_defaults()
    out = {}
    for k in SETTING_KEYS:
        v = doc.get(k)
        if isinstance(v, str):
            v = v.strip()
        if v in (None, "", []):
            out[k] = defaults.get(k, "")
        else:
            out[k] = v
    return out


async def get_setting(key: str):
    return (await get_settings()).get(key, "")


async def get_bool_setting(key: str, default: bool = False) -> bool:
    value = await get_setting(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


async def update_settings(data: dict):
    clean = {k: v for k, v in data.items() if k in SETTING_KEYS}
    clean["id"] = "global"
    await db.platform_settings.update_one({"id": "global"}, {"$set": clean}, upsert=True)
    return await get_settings()


async def get_plans() -> list:
    """Merge defaults with admin-configured overrides (price/features/cta by id)."""
    overrides = await get_setting("plans_override") or []
    if not isinstance(overrides, list):
        overrides = []
    by_id = {o.get("id"): o for o in overrides if isinstance(o, dict) and o.get("id")}
    merged = []
    for plan in DEFAULT_PLANS:
        p = copy.deepcopy(plan)
        o = by_id.get(p["id"], {})
        for key in ("name", "price_monthly", "price_yearly", "features", "cta", "featured"):
            if key in o and o[key] not in (None, ""):
                p[key] = o[key]
        merged.append(p)
    return merged
