import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent / ".env")

from db import db
import auth as authlib
import models as m

AVATARS = [
    "https://images.unsplash.com/photo-1680444602159-cd8b9abe4698?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHwxfHxzbWlsaW5nJTIwZmFjZSUyMHBvcnRyYWl0fGVufDB8fHx8MTc4Njc4NTY5Mnww&ixlib=rb-4.1.0&q=85",
    "https://images.unsplash.com/photo-1567516364473-233c4b6fcfbe?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHw0fHxzbWlsaW5nJTIwZmFjZSUyMHBvcnRyYWl0fGVufDB8fHx8MTc4Njc4NTY5Mnww&ixlib=rb-4.1.0&q=85",
    "https://images.unsplash.com/photo-1623717217554-72ca676de535?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHwzfHxzbWlsaW5nJTIwZmFjZSUyMHBvcnRyYWl0fGVufDB8fHx8MTc4Njc4NTY5Mnww&ixlib=rb-4.1.0&q=85",
]

DEMO = [
    ("Sarah", "Johnson", "Acme Corp", "VP of Marketing", 5,
     "Working with this team completely transformed our workflow. We went from spending hours collecting feedback to having a beautiful wall of testimonials on our site in a single afternoon. Our conversion rate jumped 34%.", True, True),
    ("Marcus", "Lee", "Bright Labs", "Founder", 5,
     "The video testimonial recording is ridiculously smooth. My customers just click a link and record — no apps, no friction. This is exactly what a modern SaaS should feel like.", False, True),
    ("Elena", "Rodriguez", "Studio Nine", "Creative Director", 5,
     "I've tried three other tools and none came close. The embed widgets look stunning and match our brand perfectly. Support is fantastic too.", True, False),
    ("David", "Chen", "GrowthPad", "Head of Product", 4,
     "Setup took two minutes. The approval workflow keeps everything organized and the analytics help me understand what social proof actually converts.", False, False),
    ("Priya", "Nair", "Coachly", "Business Coach", 5,
     "As a coach, social proof is everything. Now every happy client leaves a testimonial in under a minute. Game changer for my funnel.", False, True),
    ("Tom", "Wallace", "Ship&Co", "COO", 5,
     "The masonry wall of love on our homepage is the first thing visitors mention. Beautiful, fast, and dead simple to manage.", False, False),
]


async def main():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@testify.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")

    user = await db.users.find_one({"email": admin_email})
    if not user:
        uid = m.gen_id("user_")
        user = {
            "id": uid, "name": "Alex Founder", "email": admin_email,
            "password_hash": authlib.hash_password(admin_password),
            "avatar": None, "auth_provider": "email", "role": "owner",
            "email_verified": True, "onboarded": True,
            "created_at": m.now_iso(), "updated_at": m.now_iso(),
        }
        await db.users.insert_one(user)
        print("Created admin user")
    else:
        await db.users.update_one({"id": user["id"]}, {"$set": {"onboarded": True, "password_hash": authlib.hash_password(admin_password)}})
        print("Admin exists, updated")

    ws = await db.workspaces.find_one({"owner_id": user["id"]})
    if not ws:
        ws = {
            "id": m.gen_id("ws_"), "owner_id": user["id"], "name": "Testify Demo",
            "slug": "testify-demo", "logo_url": None, "primary_color": "#ff5722",
            "secondary_color": "#151515", "button_color": "#ff5722", "plan": "pro",
            "created_at": m.now_iso(), "updated_at": m.now_iso(),
        }
        await db.workspaces.insert_one(ws)
        await db.workspace_members.insert_one({"id": m.gen_id("wm_"), "workspace_id": ws["id"], "user_id": user["id"], "role": "owner", "created_at": m.now_iso()})
        print("Created workspace")

    col = await db.collections.find_one({"workspace_id": ws["id"]})
    if not col:
        col = {
            "id": m.gen_id("col_"), "workspace_id": ws["id"], "name": "Customer Love",
            "slug": "testify-demo", "headline": "We'd love to hear from you!",
            "description": "Your feedback helps us help more founders build trust with social proof.",
            "logo_url": None, "brand_color": "#ff5722", "background_color": "#0a0a0a",
            "welcome_video_url": None, "allow_video": True, "allow_text": True,
            "require_email": True, "require_company": False, "require_role": False,
            "collect_rating": True, "custom_questions": ["What problem did we help you solve?"],
            "thank_you_message": "Thank you! Your testimonial means the world to us. ❤️",
            "redirect_url": None, "published": True, "views": 428, "submissions": 6,
            "created_at": m.now_iso(), "updated_at": m.now_iso(),
        }
        await db.collections.insert_one(col)
        print("Created collection")

    existing_t = await db.testimonials.count_documents({"workspace_id": ws["id"]})
    if existing_t == 0:
        for i, (fn, ln, comp, role, rating, text, is_video, featured) in enumerate(DEMO):
            status = "approved" if i < 5 else "pending"
            await db.testimonials.insert_one({
                "id": m.gen_id("tst_"), "workspace_id": ws["id"], "collection_id": col["id"],
                "first_name": fn, "last_name": ln, "email": f"{fn.lower()}@example.com",
                "company": comp, "role": role, "website": "", "avatar_url": AVATARS[i % 3],
                "text": text, "video_url": None,
                "video_thumbnail_url": None, "rating": rating, "status": status,
                "featured": featured, "consent": True,
                "consent_text": "I give Testify Demo permission to use this testimonial.",
                "consent_at": m.now_iso(), "custom_answers": {}, "tags": (["Featured"] if featured else []) + (["SaaS"] if i % 2 == 0 else ["Startup"]),
                "notes": "", "source": col["name"], "submitted_at": m.now_iso(),
                "approved_at": m.now_iso() if status == "approved" else None,
                "created_at": m.now_iso(), "updated_at": m.now_iso(),
            })
        for tag in ["Featured", "SaaS", "Startup", "Enterprise", "Homepage"]:
            await db.tags.insert_one({"id": m.gen_id("tag_"), "workspace_id": ws["id"], "name": tag, "created_at": m.now_iso()})
        print("Created demo testimonials + tags")

    w = await db.widgets.find_one({"workspace_id": ws["id"]})
    if not w:
        await db.widgets.insert_one({
            "id": m.gen_id("wid_"), "workspace_id": ws["id"], "name": "Homepage Wall of Love",
            "type": "grid",
            "configuration": {"source": "approved", "tag": None, "theme": "dark", "columns": 3,
                              "limit": 9, "show_photo": True, "show_company": True, "show_role": True,
                              "show_rating": True, "show_video": True, "accent_color": "#ff5722",
                              "border_radius": 16, "autoplay": True},
            "loads": 112, "created_at": m.now_iso(), "updated_at": m.now_iso(),
        })
        print("Created widget")

    print("SEED COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
