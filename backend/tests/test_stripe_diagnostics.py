"""Iteration 4 — Stripe checkout error messaging + /api/admin/stripe-status diagnostic.

Two layers:
  * HTTP tests against the running backend (STRIPE_SECRET_KEY blank in backend/.env)
  * In-process TestClient tests where stripe.api_key / stripe.Price.list are monkeypatched
    so both the "no matching price" and "AuthenticationError" branches are exercised
    WITHOUT hitting the real Stripe API.
"""
import importlib
import sys
from pathlib import Path

import pytest
import stripe
from fastapi.testclient import TestClient

from conftest import API, ADMIN_EMAIL, ADMIN_PASSWORD, auth

BACKEND_DIR = Path("/app/backend")
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

EXPECTED_KEYS = ["pro_monthly", "pro_yearly", "business_monthly", "business_yearly"]


# ---------- Layer 1: live HTTP (real deployed backend, STRIPE_SECRET_KEY blank) ----------
class TestLiveHttp:
    def test_checkout_invalid_lookup_key_returns_400(self, api, free_user):
        r = api.post(f"{API}/payments/checkout",
                     json={"lookup_key": "ultra_yearly", "origin_url": "http://localhost:3000"},
                     headers=auth(free_user["token"]))
        assert r.status_code == 400, r.text
        assert r.json()["detail"] == "Invalid plan"

    def test_checkout_without_stripe_key_mentions_stripe_secret_key(self, api, free_user):
        r = api.post(f"{API}/payments/checkout",
                     json={"lookup_key": "pro_monthly", "origin_url": "http://localhost:3000"},
                     headers=auth(free_user["token"]))
        assert r.status_code == 500, r.text
        assert "STRIPE_SECRET_KEY" in r.json()["detail"]

    def test_checkout_requires_auth(self, api):
        r = api.post(f"{API}/payments/checkout",
                     json={"lookup_key": "pro_monthly", "origin_url": "http://localhost:3000"})
        assert r.status_code in (401, 403), r.text

    def test_stripe_status_nonadmin_403(self, api, nonadmin_user):
        r = api.get(f"{API}/admin/stripe-status", headers=auth(nonadmin_user["token"]))
        assert r.status_code == 403, r.text

    def test_stripe_status_unauthenticated(self, api):
        r = api.get(f"{API}/admin/stripe-status")
        assert r.status_code in (401, 403), r.text

    def test_stripe_status_admin_no_key(self, api, admin_token):
        r = api.get(f"{API}/admin/stripe-status", headers=auth(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["configured"] is False
        assert "STRIPE_SECRET_KEY" in body.get("detail", "")

    def test_plans_regression(self, api):
        r = api.get(f"{API}/plans")
        assert r.status_code == 200, r.text
        plans = r.json()
        free = [p for p in plans if p.get("id") == "free" or p.get("name", "").lower() == "free"]
        assert free, plans
        assert any("Up to 5 testimonials" in f for f in free[0]["features"]), free[0]


# ---------- Layer 2: in-process with monkeypatched stripe ----------
@pytest.fixture(scope="module")
def server_mod():
    mod = sys.modules.get("server") or importlib.import_module("server")
    return mod


@pytest.fixture(scope="module")
def client(server_mod):
    with TestClient(server_mod.app) as c:
        yield c


@pytest.fixture(scope="module")
def inproc_admin_headers(client):
    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def inproc_user_headers(client):
    import uuid
    email = f"test_inproc_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/register", json={"name": "TEST_ InProc", "email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


class _EmptyList:
    data = []


class TestMonkeypatchedStripe:
    def test_checkout_no_price_message_is_actionable(self, client, inproc_user_headers, monkeypatch):
        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(lambda cls, **kw: _EmptyList()))
        r = client.post("/api/payments/checkout",
                        json={"lookup_key": "pro_monthly", "origin_url": "http://localhost:3000"},
                        headers=inproc_user_headers)
        assert r.status_code == 500, r.text
        detail = r.json()["detail"]
        assert "lookup_key" in detail, detail
        assert "setup_stripe.py" in detail, detail
        assert "pro_monthly" in detail, detail

    def test_checkout_auth_error_branch(self, client, inproc_user_headers, monkeypatch):
        def boom(cls, **kw):
            raise stripe.error.AuthenticationError("Invalid API Key provided")
        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(boom))
        r = client.post("/api/payments/checkout",
                        json={"lookup_key": "pro_yearly", "origin_url": "http://localhost:3000"},
                        headers=inproc_user_headers)
        assert r.status_code == 500, r.text
        assert "STRIPE_SECRET_KEY" in r.json()["detail"]

    def test_checkout_invalid_plan_short_circuits_before_stripe(self, client, inproc_user_headers, monkeypatch):
        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        r = client.post("/api/payments/checkout",
                        json={"lookup_key": "ultra_yearly", "origin_url": "http://localhost:3000"},
                        headers=inproc_user_headers)
        assert r.status_code == 400
        assert r.json()["detail"] == "Invalid plan"

    def test_status_fake_test_key_reports_missing_all(self, client, inproc_admin_headers, monkeypatch):
        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(lambda cls, **kw: _EmptyList()))
        r = client.get("/api/admin/stripe-status", headers=inproc_admin_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["configured"] is True
        assert b["mode"] == "test"
        assert sorted(b["lookup_keys"].keys()) == sorted(EXPECTED_KEYS)
        assert all(v["exists"] is False for v in b["lookup_keys"].values())
        assert sorted(b["missing"]) == sorted(EXPECTED_KEYS)
        assert "setup_stripe.py" in b["action"]

    def test_status_live_key_mode_detection(self, client, inproc_admin_headers, monkeypatch):
        monkeypatch.setattr(stripe, "api_key", "sk_live_fake_for_testing", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(lambda cls, **kw: _EmptyList()))
        r = client.get("/api/admin/stripe-status", headers=inproc_admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["mode"] == "live"

    def test_status_auth_error_does_not_crash(self, client, inproc_admin_headers, monkeypatch):
        def boom(cls, **kw):
            raise stripe.error.AuthenticationError("Invalid API Key provided: sk_test_***")
        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(boom))
        r = client.get("/api/admin/stripe-status", headers=inproc_admin_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["configured"] is True
        assert b["mode"] == "test"
        assert "error" in b and b["error"], b
        assert "authentication failed" in b["error"].lower()

    def test_status_prices_found_reports_amounts(self, client, inproc_admin_headers, monkeypatch):
        class FakePrice:
            id = "price_123"
            unit_amount = 1900
            currency = "usd"

        class FoundList:
            data = [FakePrice()]

        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(lambda cls, **kw: FoundList()))
        r = client.get("/api/admin/stripe-status", headers=inproc_admin_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["missing"] == []
        assert b["lookup_keys"]["pro_monthly"] == {
            "exists": True, "price_id": "price_123", "amount": 19.0, "currency": "usd",
        }
        assert b["action"] == "All good."

    def test_status_generic_exception_does_not_crash(self, client, inproc_admin_headers, monkeypatch):
        def boom(cls, **kw):
            raise RuntimeError("network down")
        monkeypatch.setattr(stripe, "api_key", "whatever_key", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(boom))
        r = client.get("/api/admin/stripe-status", headers=inproc_admin_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["mode"] == "unknown"
        assert "network down" in b["error"]

    def test_status_nonadmin_403_inproc(self, client, inproc_user_headers, monkeypatch):
        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        r = client.get("/api/admin/stripe-status", headers=inproc_user_headers)
        assert r.status_code == 403, r.text
