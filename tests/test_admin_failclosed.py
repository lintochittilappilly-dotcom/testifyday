"""Fix 4: with ADMIN_EMAIL unset the backend must fail closed.

This module rewrites /app/backend/.env (ADMIN_EMAIL commented out), restarts the
backend, registers a user with the old hardcoded fallback email admin@testify.com
and asserts they get NO admin powers. The env file and backend are restored in the
fixture teardown.
"""
import shutil
import subprocess
import time
import uuid

import pytest
import requests

from conftest import API, auth

ENV_PATH = "/app/backend/.env"
BACKUP = "/tmp/backend_env_backup_it2"


def _restart_and_wait():
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True, timeout=90)
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            if requests.get(f"{API}/health", timeout=3).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    pytest.fail("backend did not come back up after restart")


@pytest.fixture(scope="module")
def no_admin_email_backend():
    shutil.copyfile(ENV_PATH, BACKUP)
    with open(ENV_PATH) as f:
        lines = f.read().splitlines()
    patched = ["#" + ln if ln.startswith("ADMIN_EMAIL=") else ln for ln in lines]
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(patched) + "\n")
    _restart_and_wait()
    yield
    shutil.copyfile(BACKUP, ENV_PATH)
    _restart_and_wait()


class TestAdminFailClosed:
    def test_hardcoded_fallback_email_gets_no_admin(self, no_admin_email_backend):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        email = "admin@testify.com"
        password = "TestPass123!"
        # register (or login if it already exists)
        r = s.post(f"{API}/auth/register", json={"name": "TEST_ Fallback", "email": email, "password": password})
        if r.status_code != 200:
            r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"could not obtain a session for {email}: {r.status_code} {r.text[:300]}"
        token = r.json()["token"]

        # register response must not flag admin
        assert r.json()["user"]["is_admin"] is False, "register/login response marks admin@testify.com as admin"

        # /api/auth/me must not flag admin
        me = s.get(f"{API}/auth/me", headers=auth(token))
        assert me.status_code == 200, me.text
        assert me.json()["is_admin"] is False, "public_user() still flags admin@testify.com as admin"

        # admin route must 403
        st = s.get(f"{API}/admin/settings", headers=auth(token))
        assert st.status_code == 403, f"expected 403 from /api/admin/settings, got {st.status_code}: {st.text[:200]}"

        pu = s.put(f"{API}/admin/settings", headers=auth(token), json={"promo_banner_text": "TEST_pwn"})
        assert pu.status_code == 403, f"expected 403 from PUT /api/admin/settings, got {pu.status_code}"

    def test_cleanup_fallback_user(self, no_admin_email_backend):
        from conftest import DB_NAME, MONGO_URL
        from pymongo import MongoClient
        c = MongoClient(MONGO_URL)
        db = c[DB_NAME]
        u = db.users.find_one({"email": "admin@testify.com"}, {"_id": 0, "id": 1})
        if u:
            ws_ids = [w["id"] for w in db.workspaces.find({"owner_id": u["id"]}, {"id": 1})]
            db.collections.delete_many({"workspace_id": {"$in": ws_ids}})
            db.testimonials.delete_many({"workspace_id": {"$in": ws_ids}})
            db.workspaces.delete_many({"id": {"$in": ws_ids}})
            db.users.delete_one({"id": u["id"]})
        c.close()
        assert True
