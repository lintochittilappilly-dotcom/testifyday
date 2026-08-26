import os
import copy
from db import db

DEFAULT_PLANS = [
    {
        "id": "free", "name": "Free", "price_monthly": 0, "price_yearly": 0,
        "lookup_monthly": None, "lookup_yearly": None,
        "period_free": "forever",
        "features": [
            "1 collection page",
            "Up to 5 testimonials",
            "Written or image testimonials",
            "1 basic widget",
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
            "Unlimited widgets",
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
]


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
    }


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
