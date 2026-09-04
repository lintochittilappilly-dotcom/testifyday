"""Admin Analytics dashboard endpoints (iteration 12).

Covers: /api/admin/stats/overview, /api/admin/users, /api/admin/payments,
/api/admin/collections/top, revenue/conversion aggregation, and the
non-blocking admin signup notification on POST /api/auth/register.
"""
import uuid
from datetime import datetime, timezone

import pytest
import requests

from conftest import API, ADMIN_EMAIL, auth, _register


# ---------- auth guards ----------
class TestAdminGuards:
    ENDPOINTS = [
        "/admin/stats/overview",
        "/admin/users",
        "/admin/payments",
        "/admin/collections/top",
    ]

    @pytest.mark.parametrize("path", ENDPOINTS)
    def test_unauthenticated_returns_401(self, api, path):
        r = requests.get(f"{API}{path}")
        assert r.status_code == 401, f"{path} -> {r.status_code}: {r.text[:200]}"

    @pytest.mark.parametrize("path", ENDPOINTS)
    def test_nonadmin_returns_403(self, api, nonadmin_user, path):
        r = requests.get(f"{API}{path}", headers=auth(nonadmin_user["token"]))
        assert r.status_code == 403, f"{path} -> {r.status_code}: {r.text[:200]}"
        assert "dmin" in (r.json().get("detail") or "")

    @pytest.mark.parametrize("path", ENDPOINTS)
    def test_bad_token_returns_401(self, api, path):
        r = requests.get(f"{API}{path}", headers=auth("not-a-real-token"))
        assert r.status_code == 401, f"{path} -> {r.status_code}"


# ---------- overview shape ----------
class TestOverview:
    def test_overview_shape(self, api, admin_token):
        r = requests.get(f"{API}/admin/stats/overview", headers=auth(admin_token))
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("signups", "payments", "revenue", "plans", "conversions", "content"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["signups"]["total"], int) and d["signups"]["total"] >= 1
        assert isinstance(d["signups"]["this_month"], int)
        assert d["signups"]["admin_email"] == (ADMIN_EMAIL or "").lower()
        assert set(("paid", "pending_or_failed")).issubset(d["payments"].keys())
        assert set(("all_time", "this_month", "by_currency")).issubset(d["revenue"].keys())
        assert isinstance(d["revenue"]["by_currency"], dict)
        assert set(("free", "pro", "business")).issubset(d["plans"].keys())
        for k in ("pro", "business", "any_paid", "free_to_paid_rate", "pro_to_business"):
            assert k in d["conversions"], f"conversions.{k} missing"
        for k in ("collections", "testimonials_total", "testimonials_this_month"):
            assert k in d["content"], f"content.{k} missing"
        assert "_id" not in str(d)

    def test_signup_increments_total(self, api, admin_token):
        before = requests.get(f"{API}/admin/stats/overview", headers=auth(admin_token)).json()["signups"]["total"]
        u = _register(api, "sig")
        assert u["user"]["email"]
        after = requests.get(f"{API}/admin/stats/overview", headers=auth(admin_token)).json()["signups"]["total"]
        assert after == before + 1, f"signups.total {before} -> {after}"


# ---------- users ----------
class TestAdminUsers:
    def test_lists_admin_user(self, api, admin_token):
        r = requests.get(f"{API}/admin/users", headers=auth(admin_token))
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert isinstance(d["users"], list) and d["count"] == len(d["users"])
        emails = [u["email"] for u in d["users"]]
        assert ADMIN_EMAIL in emails
        row = next(u for u in d["users"] if u["email"] == ADMIN_EMAIL)
        for k in ("id", "name", "auth_provider", "created_at", "onboarded", "workspace_count", "plan"):
            assert k in row, f"user row missing {k}"
        assert all("password_hash" not in u for u in d["users"])
        assert "_id" not in str(d)

    def test_limit_param(self, api, admin_token):
        r = requests.get(f"{API}/admin/users?limit=1", headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_new_user_appears(self, api, admin_token):
        u = _register(api, "listed")
        r = requests.get(f"{API}/admin/users", headers=auth(admin_token))
        row = next((x for x in r.json()["users"] if x["email"] == u["email"]), None)
        assert row is not None, "freshly registered user missing from /admin/users"
        assert row["plan"] == "free"
        assert row["workspace_count"] >= 1


# ---------- payments ----------
class TestAdminPayments:
    def test_payments_shape(self, api, admin_token):
        r = requests.get(f"{API}/admin/payments", headers=auth(admin_token))
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert isinstance(d["payments"], list) and d["count"] == len(d["payments"])

    @pytest.mark.parametrize("status", ["paid", "pending", "failed"])
    def test_status_filter(self, api, admin_token, status):
        r = requests.get(f"{API}/admin/payments?status={status}", headers=auth(admin_token))
        assert r.status_code == 200, r.text[:300]
        for p in r.json()["payments"]:
            assert p["payment_status"] == status

    def test_unknown_status_returns_400(self, api, admin_token):
        bogus = requests.get(f"{API}/admin/payments?status=bogus", headers=auth(admin_token))
        assert bogus.status_code == 400
        assert "paid" in bogus.json()["detail"].lower()


# ---------- collections/top ----------
class TestTopCollections:
    def test_shape(self, api, admin_token):
        r = requests.get(f"{API}/admin/collections/top", headers=auth(admin_token))
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert isinstance(d["collections"], list)
        counts = [c["testimonial_count"] for c in d["collections"]]
        assert counts == sorted(counts, reverse=True), "not sorted desc"
        for c in d["collections"]:
            for k in ("collection_id", "collection_name", "slug", "workspace_name", "workspace_plan", "testimonial_count"):
                assert k in c


# ---------- revenue / conversion aggregation with seeded transactions ----------
class TestRevenueAggregation:
    def test_seeded_paid_transactions_roll_up(self, api, admin_token, mongo):
        # Use a fresh NON-admin workspace so conversions are counted
        # (admin's own workspace is excluded from conversion math).
        admin_user = mongo.users.find_one({"email": ADMIN_EMAIL}, {"id": 1})
        assert admin_user, "admin user not seeded"
        fake_ws_id = f"TEST_ws_{uuid.uuid4().hex[:8]}"
        fake_owner_id = f"TEST_usr_{uuid.uuid4().hex[:8]}"
        nowiso = datetime.now(timezone.utc).isoformat()
        mongo.users.insert_one({
            "id": fake_owner_id, "email": f"convtest_{fake_owner_id}@example.com",
            "name": "Conv Test", "auth_provider": "email",
            "password_hash": "x", "created_at": nowiso, "updated_at": nowiso,
            "onboarded": True,
        })
        mongo.workspaces.insert_one({
            "id": fake_ws_id, "owner_id": fake_owner_id, "name": "Conv WS",
            "slug": f"conv-{fake_ws_id[-6:]}", "plan": "business",
            "primary_color": "#000000", "created_at": nowiso, "updated_at": nowiso,
        })
        ws_id = fake_ws_id

        base = requests.get(f"{API}/admin/stats/overview", headers=auth(admin_token)).json()
        b_rev = base["revenue"]["all_time"]
        b_usd = base["revenue"]["by_currency"].get("usd", 0)
        b_paid = base["payments"]["paid"]
        b_pro = base["conversions"]["pro"]
        b_biz = base["conversions"]["business"]
        b_ladder = base["conversions"]["pro_to_business"]
        b_month = base["revenue"]["this_month"]

        sid_pro = f"TEST_sess_{uuid.uuid4().hex[:8]}"
        sid_biz = f"TEST_sess_{uuid.uuid4().hex[:8]}"
        try:
            mongo.payment_transactions.insert_one({
                "id": f"TEST_pt_{uuid.uuid4().hex[:8]}", "session_id": sid_pro,
                "user_id": fake_owner_id, "workspace_id": ws_id, "plan": "pro",
                "lookup_key": "pro_monthly", "amount": 2900, "currency": "usd",
                "status": "complete", "payment_status": "paid",
                "created_at": nowiso, "updated_at": nowiso,
            })
            d = requests.get(f"{API}/admin/stats/overview", headers=auth(admin_token)).json()
            assert round(d["revenue"]["all_time"] - b_rev, 2) == 29.00, d["revenue"]
            assert round(d["revenue"]["by_currency"]["usd"] - b_usd, 2) == 29.00
            assert d["payments"]["paid"] == b_paid + 1
            # pro conversion counts distinct non-admin workspaces that ever paid for pro
            assert d["conversions"]["pro"] == b_pro + 1
            assert d["conversions"]["pro_to_business"] == b_ladder

            mongo.payment_transactions.insert_one({
                "id": f"TEST_pt_{uuid.uuid4().hex[:8]}", "session_id": sid_biz,
                "user_id": fake_owner_id, "workspace_id": ws_id, "plan": "business",
                "lookup_key": "business_monthly", "amount": 9900, "currency": "usd",
                "status": "complete", "payment_status": "paid",
                "created_at": nowiso, "updated_at": nowiso,
            })
            d2 = requests.get(f"{API}/admin/stats/overview", headers=auth(admin_token)).json()
            assert round(d2["revenue"]["all_time"] - b_rev, 2) == 128.00, d2["revenue"]
            assert round(d2["revenue"]["by_currency"]["usd"] - b_usd, 2) == 128.00
            assert d2["payments"]["paid"] == b_paid + 2
            assert d2["conversions"]["business"] == b_biz + 1
            assert d2["conversions"]["pro_to_business"] == b_ladder + 1, (
                "workspace that paid for pro then business should count in the ladder")

            # revenue this_month should include both (updated_at = now)
            assert round(d2["revenue"]["this_month"] - b_month, 2) == 128.00, d2["revenue"]

            # /admin/payments should surface them
            pays = requests.get(f"{API}/admin/payments?status=paid", headers=auth(admin_token)).json()["payments"]
            seeded = [p for p in pays if p["session_id"] in (sid_pro, sid_biz)]
            assert len(seeded) == 2, "seeded paid rows not returned by /admin/payments"
            amounts = sorted(p["amount"] for p in seeded)
            assert amounts == [29.0, 99.0], amounts
        finally:
            mongo.payment_transactions.delete_many({"session_id": {"$in": [sid_pro, sid_biz]}})
            mongo.workspaces.delete_one({"id": fake_ws_id})
            mongo.users.delete_one({"id": fake_owner_id})

        after = requests.get(f"{API}/admin/stats/overview", headers=auth(admin_token)).json()
        assert round(after["revenue"]["all_time"], 2) == round(b_rev, 2), "cleanup did not restore revenue"


# ---------- register stays non-blocking with admin email hook ----------
class TestRegisterNotification:
    def test_register_returns_200(self, api):
        email = f"test_notify_{uuid.uuid4().hex[:8]}@example.com"
        r = api.post(f"{API}/auth/register", json={"name": "TEST_ Notify", "email": email, "password": "TestPass123!"})
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        body = r.json()
        assert body["token"] and body["user"]["email"] == email
        assert body["user"]["is_admin"] is False
