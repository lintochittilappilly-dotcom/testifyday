import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request

from google.oauth2 import id_token
from google.auth.transport import requests as g_requests

from db import db

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def _extract_token(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.cookies.get("access_token")


async def get_current_user(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_user_workspace(user: dict) -> dict:
    active_id = user.get("active_workspace_id")
    if active_id:
        mem = await db.workspace_members.find_one({"workspace_id": active_id, "user_id": user["id"]})
        if mem:
            ws = await db.workspaces.find_one({"id": active_id}, {"_id": 0})
            if ws:
                return ws
    ws = await db.workspaces.find_one({"owner_id": user["id"]}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


async def get_ws_role(user_id: str, workspace_id: str) -> str:
    mem = await db.workspace_members.find_one({"workspace_id": workspace_id, "user_id": user_id})
    return mem.get("role") if mem else None


def verify_google_id_token(credential: str) -> dict:
    """Verify a Google ID token (JWT) obtained via Google Identity Services on the frontend.

    Returns a dict with at least: email, name, picture.
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="Google login is not configured")
    try:
        info = id_token.verify_oauth2_token(credential, g_requests.Request(), client_id)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google credential: {e}")
    if not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google email is not verified")
    return {
        "email": info["email"],
        "name": info.get("name") or info["email"].split("@")[0],
        "picture": info.get("picture"),
    }


# Brute force protection

async def check_lockout(identifier: str):
    rec = await db.login_attempts.find_one({"identifier": identifier})
    if rec and rec.get("count", 0) >= 5:
        locked_until = rec.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again in 15 minutes.")


async def record_failed_login(identifier: str):
    rec = await db.login_attempts.find_one({"identifier": identifier})
    count = (rec.get("count", 0) if rec else 0) + 1
    update = {"count": count}
    if count >= 5:
        update["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)


async def clear_login_attempts(identifier: str):
    await db.login_attempts.delete_one({"identifier": identifier})


async def seed_admin():
    """Ensure an admin user exists with the configured credentials.

    Creates the admin + a default workspace on first run. Updates the password
    if it doesn't match the environment on subsequent runs (idempotent).
    """
    from models import gen_id, now_iso
    from pymongo.errors import DuplicateKeyError

    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        return
    admin_email = admin_email.lower()
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        uid = gen_id("user_")
        await db.users.insert_one({
            "id": uid,
            "name": "Admin",
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "avatar": None,
            "auth_provider": "email",
            "role": "owner",
            "email_verified": True,
            "onboarded": True,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
        ws_id = gen_id("ws_")
        try:
            await db.workspaces.insert_one({
                "id": ws_id, "owner_id": uid, "name": "Admin Workspace",
                "slug": f"admin-{ws_id[-6:]}", "logo_url": None,
                "primary_color": "#ff5722", "secondary_color": "#151515",
                "button_color": "#ff5722", "plan": "business",
                "created_at": now_iso(), "updated_at": now_iso(),
            })
            await db.workspace_members.insert_one({
                "id": gen_id("wm_"), "workspace_id": ws_id, "user_id": uid,
                "role": "owner", "created_at": now_iso(),
            })
        except DuplicateKeyError:
            pass
        return
    # Rotate password if env changed
    if not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one(
            {"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}}
        )
