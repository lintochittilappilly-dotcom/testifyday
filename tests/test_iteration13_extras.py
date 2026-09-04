"""Iteration-13 supplementary checks (written by testing agent).

Covers:
- register latency parity across admin_notify_mode instant/daily/off (fire-and-forget)
- conversions.excludes_admin flag + admin-owned paid workspace does NOT inflate conversions
- invalid admin_notify_mode value handling
"""
import time
import uuid

import pytest
import requests

from conftest import API, ADMIN_EMAIL, auth


def _set_mode(admin_token, mode):
    r = requests.put(f"{API}/admin/settings", headers=auth(admin_token), json={"admin_notify_mode": mode})
    assert r.status_code == 200, r.text[:300]


def _overview(admin_token):
    r = requests.get(f"{API}/admin/stats/overview", headers=auth(admin_token))
    assert r.status_code == 200, r.text[:300]
    return r.json()


# ---------- background email must not block register ----------
class TestRegisterNonBlocking:
    @pytest.mark.parametrize("mode", ["instant", "daily", "off"])
    def test_register_fast_in_every_mode(self, api, admin_token, mode):
        _set_mode(admin_token, mode)
        try:
            email = f"test_lat_{mode}_{uuid.uuid4().hex[:8]}@example.com"
            t0 = time.time()
            r = api.post(f"{API}/auth/register", json={"name": "TEST_ Latency", "email": email, "password": "TestPass123!"})
            elapsed = time.time() - t0
            assert r.status_code == 200, r.text[:300]
            body = r.json()
            assert body["user"]["email"] == email
            assert isinstance(body["token"], str) and body["token"]
            assert elapsed < 2.0, f"register took {elapsed:.2f}s in mode={mode}"
        finally:
            _set_mode(admin_token, "instant")

    def test_mode_after_all_runs_is_instant(self, admin_token):
        r = requests.get(f"{API}/admin/notifications/status", headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["mode"] == "instant"


# ---------- conversion math excludes admin workspace ----------
class TestExcludeAdminConversions:
    def test_excludes_admin_flag_true(self, admin_token):
        d = _overview(admin_token)
        assert d["conversions"]["excludes_admin"] is True, "ADMIN_EMAIL configured => excludes_admin must be True"
        assert d["signups"]["admin_email"] == (ADMIN_EMAIL or "").lower()

    def test_admin_paid_payment_does_not_change_conversions(self, admin_token, mongo):
        admin_user = mongo.users.find_one({"email": (ADMIN_EMAIL or "").lower()}, {"id": 1})
        assert admin_user, "admin user must be seeded"
        admin_ws = mongo.workspaces.find_one({"owner_id": admin_user["id"]}, {"id": 1})
        assert admin_ws, "admin should own at least one workspace"

        before = _overview(admin_token)["conversions"]
        sid = f"TEST_sess_{uuid.uuid4().hex[:10]}"
        mongo.payment_transactions.insert_one({
            "session_id": sid,
            "user_id": admin_user["id"],
            "workspace_id": admin_ws["id"],
            "plan": "pro",
            "lookup_key": "pro_monthly",
            "amount": 1900,
            "currency": "usd",
            "status": "complete",
            "payment_status": "paid",
            "created_at": "2026-07-01T00:00:00+00:00",
            "updated_at": "2026-07-01T00:00:00+00:00",
        })
        try:
            after = _overview(admin_token)["conversions"]
            assert after["pro"] == before["pro"], "admin's own paid pro workspace must not count as a conversion"
            assert after["any_paid"] == before["any_paid"]
        finally:
            mongo.payment_transactions.delete_many({"session_id": sid})

    def test_nonadmin_paid_payment_does_count(self, admin_token, mongo, api):
        user = api.post(f"{API}/auth/register", json={
            "name": "TEST_ Conv", "email": f"test_conv_{uuid.uuid4().hex[:8]}@example.com", "password": "TestPass123!"
        })
        assert user.status_code == 200
        uid = user.json()["user"]["id"]
        ws_doc = mongo.workspaces.find_one({"owner_id": uid}, {"id": 1})
        assert ws_doc, "new user should get a default workspace"
        ws_id = ws_doc["id"]

        before = _overview(admin_token)["conversions"]
        sid = f"TEST_sess_{uuid.uuid4().hex[:10]}"
        mongo.payment_transactions.insert_one({
            "session_id": sid,
            "user_id": user.json()["user"]["id"],
            "workspace_id": ws_id,
            "plan": "pro",
            "lookup_key": "pro_monthly",
            "amount": 1900,
            "currency": "usd",
            "status": "complete",
            "payment_status": "paid",
            "created_at": "2026-07-01T00:00:00+00:00",
            "updated_at": "2026-07-01T00:00:00+00:00",
        })
        try:
            after = _overview(admin_token)["conversions"]
            assert after["pro"] == before["pro"] + 1, "non-admin paid pro workspace must count"
            assert after["any_paid"] == before["any_paid"] + 1
        finally:
            mongo.payment_transactions.delete_many({"session_id": sid})


# ---------- invalid mode ----------
class TestInvalidMode:
    def test_bogus_mode_does_not_break_status(self, admin_token):
        r = requests.put(f"{API}/admin/settings", headers=auth(admin_token), json={"admin_notify_mode": "bogus"})
        try:
            # Either it is rejected (preferred) or coerced back to a valid mode on read
            assert r.status_code in (200, 400, 422), r.text[:200]
            st = requests.get(f"{API}/admin/notifications/status", headers=auth(admin_token))
            assert st.status_code == 200
            assert st.json()["mode"] in ("instant", "daily", "off")
        finally:
            _set_mode(admin_token, "instant")
