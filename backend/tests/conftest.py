import os
import subprocess
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

# Resolve backend/.env relative to this repo first so the suite runs outside the
# original /app container layout; TESTIFY_ENV_FILE can point at an explicit file.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_CANDIDATES = [
    os.environ.get("TESTIFY_ENV_FILE"),
    os.path.join(os.path.dirname(_HERE), ".env"),
    "/app/backend/.env",
]
backend_env = {}
for _candidate in _ENV_CANDIDATES:
    if _candidate and os.path.exists(_candidate):
        backend_env = dotenv_values(_candidate)
        break

BACKEND_DIR = Path(__file__).resolve().parents[1]


def restart_backend():
    """Restart the backend under test.

    CI used `sudo supervisorctl restart backend`; TESTIFY_BACKEND_RESTART_CMD lets a
    local run supply an equivalent command (uvicorn boot script).
    """
    override = os.environ.get("TESTIFY_BACKEND_RESTART_CMD")
    if override:
        subprocess.run(override, shell=True, capture_output=True, timeout=120)
    else:
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True, timeout=90)

# In-process tests (e.g. test_upload_size_caps.py) import backend modules directly,
# and those modules read os.environ at import time. Export backend/.env values so the
# imports succeed without overriding anything already set in the process environment.
for _k, _v in backend_env.items():
    if _v is not None:
        os.environ.setdefault(_k, _v)

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = backend_env.get("ADMIN_EMAIL")
ADMIN_PASSWORD = backend_env.get("ADMIN_PASSWORD")
MONGO_URL = backend_env.get("MONGO_URL")
DB_NAME = backend_env.get("DB_NAME")


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def mongo():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME missing in backend/.env")
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="session")
def admin_token(api):
    """Admin is seeded at startup from ADMIN_EMAIL/ADMIN_PASSWORD."""
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        pytest.skip("ADMIN_EMAIL/ADMIN_PASSWORD missing in backend/.env")
    r = api.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.fail(f"Admin login failed {r.status_code}: {r.text[:300]}")
    data = r.json()
    assert data["user"]["is_admin"] is True, "seeded admin should report is_admin=True"
    return data["token"]


def _register(api, prefix="TEST_user"):
    email = f"test_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"
    r = api.post(f"{API}/auth/register", json={"name": "TEST_ User", "email": email, "password": password})
    if r.status_code != 200:
        pytest.fail(f"register failed {r.status_code}: {r.text[:300]}")
    body = r.json()
    return {"email": email, "password": password, "token": body["token"], "user": body["user"]}


@pytest.fixture(scope="session")
def free_user(api):
    """A freshly registered user -> default workspace on the free plan."""
    return _register(api, "free")


@pytest.fixture(scope="session")
def nonadmin_user(api):
    return _register(api, "nonadmin")


@pytest.fixture(scope="session")
def approved_wall(api, mongo):
    """A workspace with three approved testimonials, i.e. a live public wall."""
    user = _register(api, "wall")
    headers = auth(user["token"])
    r = api.post(
        f"{API}/onboarding",
        headers=headers,
        json={"business_name": f"TEST Wall {uuid.uuid4().hex[:6]}", "primary_color": "#ff5722"},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.fail(f"onboarding failed {r.status_code}: {r.text[:300]}")
    ws = api.get(f"{API}/workspace", headers=headers, timeout=30).json()
    docs = [
        {
            "id": f"tst_wall_{i}_{uuid.uuid4().hex[:4]}",
            "workspace_id": ws["id"],
            "collection_id": "col_wall",
            "first_name": name,
            "last_name": "",
            "email": "",
            "company": company,
            "role": "Founder",
            "text": f"TEST_Wall quote {i}",
            "rating": 5,
            "status": "approved",
            "featured": True,
            "tags": [],
            "approved_at": f"2026-01-0{i + 1}T00:00:00+00:00",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        for i, (name, company) in enumerate([("TEST_Priya", "Northwind"), ("TEST_Marcus", "Bright Labs"), ("TEST_Elena", "Studio Row")])
    ]
    mongo.testimonials.insert_many(docs)
    return {"slug": ws["slug"], "ws_id": ws["id"], "token": user["token"]}


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data(request):
    """Remove test-created users/workspaces/collections/testimonials after the session."""
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    users = list(db.users.find({"email": {"$regex": "^test_"}}, {"id": 1}))
    uids = [u["id"] for u in users]
    ws_ids = [w["id"] for w in db.workspaces.find({"owner_id": {"$in": uids}}, {"id": 1})]
    db.testimonials.delete_many({"workspace_id": {"$in": ws_ids}})
    db.collections.delete_many({"workspace_id": {"$in": ws_ids}})
    db.widgets.delete_many({"workspace_id": {"$in": ws_ids}})
    db.analytics_events.delete_many({"workspace_id": {"$in": ws_ids}})
    db.workspace_members.delete_many({"workspace_id": {"$in": ws_ids}})
    db.workspaces.delete_many({"id": {"$in": ws_ids}})
    db.users.delete_many({"id": {"$in": uids}})
    client.close()


def auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def reset_rate_limit():
    """The submit endpoint uses an in-memory rate limiter (5 calls / 300s per IP).

    Restarting the backend clears it so submit-heavy test classes stay independent.
    """
    import time

    restart_backend()
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            if requests.get(f"{API}/plans", timeout=3).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    pytest.fail("backend did not come back up after restart")
