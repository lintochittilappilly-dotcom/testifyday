import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

backend_env = dotenv_values("/app/backend/.env")

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
    import subprocess
    import time

    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True, timeout=90)
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            if requests.get(f"{API}/plans", timeout=3).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    pytest.fail("backend did not come back up after restart")
