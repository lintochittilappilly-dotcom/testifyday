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

BACKEND_DIR = Path(__file__).resolve().parents[1]
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
        """Iteration 6: not-configured branch must return the SAME normalized 6-key shape."""
        r = api.get(f"{API}/admin/stripe-status", headers=auth(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert sorted(body.keys()) == sorted(
            ["configured", "mode", "lookup_keys", "missing", "action", "error"]
        ), body
        assert "detail" not in body, "legacy 'detail' key must be removed"
        assert body["configured"] is False
        assert body["mode"] == "unknown"
        assert isinstance(body["lookup_keys"], dict)
        assert sorted(body["lookup_keys"].keys()) == sorted(EXPECTED_KEYS)
        for k, v in body["lookup_keys"].items():
            assert v == {"exists": False, "price_id": None, "amount": None, "currency": None}, (k, v)
        assert sorted(body["missing"]) == sorted(EXPECTED_KEYS)
        assert isinstance(body["action"], str) and "STRIPE_SECRET_KEY" in body["action"]
        assert "setup_stripe.py" in body["action"]
        assert body["error"] is None

    def test_plans_regression(self, api):
        r = api.get(f"{API}/plans")
        assert r.status_code == 200, r.text
        plans = r.json()
        free = [p for p in plans if p.get("id") == "free" or p.get("name", "").lower() == "free"]
        assert free, plans
        assert any("Up to 10 testimonials" in f for f in free[0]["features"]), free[0]


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


NORMALIZED_KEYS = ["configured", "mode", "lookup_keys", "missing", "action", "error"]


def assert_normalized_schema(body):
    """Iteration 6: every branch of /api/admin/stripe-status returns exactly these 6 keys."""
    assert sorted(body.keys()) == sorted(NORMALIZED_KEYS), body
    assert isinstance(body["configured"], bool)
    assert body["mode"] in ("live", "test", "unknown"), body["mode"]
    assert isinstance(body["lookup_keys"], dict)
    assert sorted(body["lookup_keys"].keys()) == sorted(EXPECTED_KEYS), body["lookup_keys"]
    for v in body["lookup_keys"].values():
        assert sorted(v.keys()) == sorted(["exists", "price_id", "amount", "currency"]), v
    assert isinstance(body["missing"], list)
    assert isinstance(body["action"], str) and body["action"]
    assert body["error"] is None or isinstance(body["error"], str)


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
        assert_normalized_schema(b)
        assert b["configured"] is True
        assert b["mode"] == "test"
        assert sorted(b["lookup_keys"].keys()) == sorted(EXPECTED_KEYS)
        assert all(v["exists"] is False for v in b["lookup_keys"].values())
        assert sorted(b["missing"]) == sorted(EXPECTED_KEYS)
        assert "setup_stripe.py" in b["action"]
        assert b["error"] is None

    def test_status_live_key_mode_detection(self, client, inproc_admin_headers, monkeypatch):
        monkeypatch.setattr(stripe, "api_key", "sk_live_fake_for_testing", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(lambda cls, **kw: _EmptyList()))
        r = client.get("/api/admin/stripe-status", headers=inproc_admin_headers)
        assert r.status_code == 200, r.text
        assert_normalized_schema(r.json())
        assert r.json()["mode"] == "live"

    def test_status_auth_error_does_not_crash(self, client, inproc_admin_headers, monkeypatch):
        def boom(cls, **kw):
            raise stripe.error.AuthenticationError("Invalid API Key provided: sk_test_***")
        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(boom))
        r = client.get("/api/admin/stripe-status", headers=inproc_admin_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert_normalized_schema(b)
        assert b["configured"] is True
        assert b["mode"] == "test"
        assert all(v["exists"] is False for v in b["lookup_keys"].values())
        assert sorted(b["missing"]) == sorted(EXPECTED_KEYS)
        assert b["error"] and b["error"].startswith("Stripe authentication failed:"), b["error"]
        assert "authentication failed" in b["error"].lower()

    def test_status_three_found_one_missing(self, client, inproc_admin_headers, monkeypatch):
        """Iteration 6: partial configuration -> missing has exactly 1 element."""
        class FakePrice:
            id = "price_abc"
            unit_amount = 2900
            currency = "usd"

        class FoundList:
            data = [FakePrice()]

        def selective(cls, **kw):
            lk = kw.get("lookup_keys", [None])[0]
            return _EmptyList() if lk == "business_yearly" else FoundList()

        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        monkeypatch.setattr(stripe.Price, "list", classmethod(selective))
        r = client.get("/api/admin/stripe-status", headers=inproc_admin_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert_normalized_schema(b)
        assert b["configured"] is True
        assert b["missing"] == ["business_yearly"], b["missing"]
        assert len(b["missing"]) == 1
        assert "setup_stripe.py" in b["action"]
        assert b["error"] is None
        assert b["lookup_keys"]["pro_monthly"]["exists"] is True
        assert b["lookup_keys"]["pro_monthly"]["amount"] == 29.0
        assert b["lookup_keys"]["business_yearly"]["exists"] is False

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
        assert_normalized_schema(b)
        assert b["missing"] == []
        assert b["error"] is None
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
        assert_normalized_schema(b)
        assert b["configured"] is True
        assert b["mode"] == "unknown"
        assert all(v["exists"] is False for v in b["lookup_keys"].values())
        assert sorted(b["missing"]) == sorted(EXPECTED_KEYS)
        assert "network down" in b["error"]

    def test_status_nonadmin_403_inproc(self, client, inproc_user_headers, monkeypatch):
        monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
        r = client.get("/api/admin/stripe-status", headers=inproc_user_headers)
        assert r.status_code == 403, r.text


# ---------- Iteration 8: 3-attempt checkout fallback chain + StripeError surfacing ----------
class _FakePrice:
    id = "price_test_iter8"
    unit_amount = 2900
    currency = "usd"


class _FoundPrices:
    data = [_FakePrice()]


class _FakeSession:
    def __init__(self, sid="cs_test_iter8", url="https://checkout.stripe.com/c/pay/cs_test_iter8"):
        self.id = sid
        self.url = url


def _patch_prices(monkeypatch):
    monkeypatch.setattr(stripe, "api_key", "sk_test_fake_for_testing", raising=False)
    monkeypatch.setattr(stripe.Price, "list", classmethod(lambda cls, **kw: _FoundPrices()))


class _SessionCreateStub:
    """Callable stub for stripe.checkout.Session.create.

    behaviours: list of either exception instances (raised) or _FakeSession (returned),
    consumed one per call.
    """

    def __init__(self, behaviours):
        self.behaviours = list(behaviours)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        b = self.behaviours.pop(0) if self.behaviours else self.behaviours
        if isinstance(b, Exception):
            raise b
        return b


@pytest.fixture
def txn_cleanup():
    ids = []
    yield ids
    try:
        from pymongo import MongoClient
        from conftest import MONGO_URL, DB_NAME
        if MONGO_URL and DB_NAME and ids:
            c = MongoClient(MONGO_URL)
            c[DB_NAME].payment_transactions.delete_many({"session_id": {"$in": ids}})
            c.close()
    except Exception as exc:  # pragma: no cover
        print(f"cleanup skipped: {exc}")


class TestCheckoutFallbackChain:
    def _post(self, client, headers):
        return client.post("/api/payments/checkout",
                           json={"lookup_key": "pro_monthly", "origin_url": "http://localhost:3000"},
                           headers=headers)

    def test_first_attempt_success_regression(self, client, inproc_user_headers, monkeypatch, txn_cleanup, mongo):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([_FakeSession("cs_test_iter8_ok")])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["session_id"] == "cs_test_iter8_ok"
        assert body["checkout_url"].startswith("https://checkout.stripe.com/")
        txn_cleanup.append(body["session_id"])
        assert len(stub.calls) == 1
        assert stub.calls[0].get("managed_payments") == {"enabled": True}
        rec = mongo.payment_transactions.find_one({"session_id": body["session_id"]})
        assert rec is not None and rec["status"] == "initiated"
        assert rec["plan"] == "pro" and rec["amount"] == 2900 and rec["currency"] == "usd"

    def test_second_attempt_automatic_tax_succeeds(self, client, inproc_user_headers, monkeypatch, txn_cleanup, mongo):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([
            stripe.error.InvalidRequestError("managed payments not enabled", "managed_payments"),
            _FakeSession("cs_test_iter8_second"),
        ])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["session_id"] == "cs_test_iter8_second"
        assert "Could not start checkout" not in r.text
        txn_cleanup.append(body["session_id"])
        assert len(stub.calls) == 2
        assert stub.calls[1].get("automatic_tax") == {"enabled": True}
        assert stub.calls[1].get("billing_address_collection") == "required"
        assert mongo.payment_transactions.find_one({"session_id": body["session_id"]}) is not None

    def test_third_attempt_minimal_succeeds(self, client, inproc_user_headers, monkeypatch, txn_cleanup, mongo):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([
            stripe.error.InvalidRequestError("managed payments unsupported", "managed_payments"),
            stripe.error.InvalidRequestError("automatic_tax not permitted", "automatic_tax"),
            _FakeSession("cs_test_iter8_third"),
        ])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["session_id"] == "cs_test_iter8_third"
        txn_cleanup.append(body["session_id"])
        assert len(stub.calls) == 3
        assert "managed_payments" not in stub.calls[2]
        assert "automatic_tax" not in stub.calls[2]
        assert mongo.payment_transactions.find_one({"session_id": body["session_id"]}) is not None

    def test_all_three_attempts_fail_returns_400_with_real_message(self, client, inproc_user_headers, monkeypatch):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([
            stripe.error.InvalidRequestError("managed payments unsupported", "managed_payments"),
            stripe.error.InvalidRequestError("automatic_tax not permitted", "automatic_tax"),
            stripe.error.InvalidRequestError("No such coupon: 'LAUNCH50'", "discounts"),
        ])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert detail.startswith("Stripe rejected the checkout:"), detail
        assert "No such coupon: 'LAUNCH50'" in detail, detail
        assert "Could not start checkout" not in r.text
        assert len(stub.calls) == 3

    def test_coupon_not_found_message_surfaced_with_admin_coupon(self, client, inproc_user_headers,
                                                                monkeypatch, server_mod):
        """Admin-configured coupon is sent as discounts and the real Stripe error is surfaced."""
        _patch_prices(monkeypatch)

        async def fake_get_setting(key, default=None):
            return "BAD_COUPON_ID" if key == "checkout_coupon_id" else default

        monkeypatch.setattr(server_mod, "get_setting", fake_get_setting)
        err = stripe.error.InvalidRequestError("No such coupon: 'BAD_COUPON_ID'", "discounts")
        stub = _SessionCreateStub([err, err, err])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert "No such coupon: 'BAD_COUPON_ID'" in detail, detail
        assert stub.calls[0].get("discounts") == [{"coupon": "BAD_COUPON_ID"}]
        assert "allow_promotion_codes" not in stub.calls[0]

    def test_rate_limit_error_returns_400_with_real_message(self, client, inproc_user_headers, monkeypatch):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([stripe.error.RateLimitError("Too many requests hit the API too quickly")])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert detail.startswith("Stripe error:"), detail
        assert "Too many requests" in detail, detail
        assert "Could not start checkout" not in r.text

    def test_api_connection_error_returns_400_with_real_message(self, client, inproc_user_headers, monkeypatch):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([stripe.error.APIConnectionError("Unexpected error communicating with Stripe")])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert detail.startswith("Stripe error:"), detail
        assert "communicating with Stripe" in detail, detail

    def test_no_transaction_row_on_failure(self, client, inproc_user_headers, monkeypatch, mongo):
        _patch_prices(monkeypatch)
        err = stripe.error.InvalidRequestError("fatal config problem", "mode")
        monkeypatch.setattr(stripe.checkout.Session, "create", _SessionCreateStub([err, err, err]))
        before = mongo.payment_transactions.count_documents({})
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400
        assert mongo.payment_transactions.count_documents({}) == before

    def test_non_invalidrequest_stripe_error_on_second_attempt(self, client, inproc_user_headers, monkeypatch):
        """Gap check: a non-InvalidRequestError StripeError raised by attempt 2/3 must not 500."""
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([
            stripe.error.InvalidRequestError("managed payments unsupported", "managed_payments"),
            stripe.error.RateLimitError("Too many requests on retry"),
        ])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400, f"expected surfaced 400, got {r.status_code}: {r.text[:300]}"
        assert "Too many requests on retry" in r.json()["detail"]


class TestIteration9EscapeHatch:
    """Iteration 9: non-InvalidRequest StripeError on ANY attempt must produce a clean 400."""

    def _post(self, client, headers):
        return client.post("/api/payments/checkout",
                           json={"lookup_key": "pro_monthly", "origin_url": "http://localhost:3000"},
                           headers=headers)

    def test_third_attempt_api_connection_error_returns_400(self, client, inproc_user_headers, monkeypatch):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([
            stripe.error.InvalidRequestError("managed payments unsupported", "managed_payments"),
            stripe.error.InvalidRequestError("automatic_tax not permitted", "automatic_tax"),
            stripe.error.APIConnectionError("Unexpected error communicating with Stripe on third try"),
        ])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
        detail = r.json()["detail"]
        assert detail.startswith("Stripe error:"), detail
        assert "third try" in detail, detail
        assert len(stub.calls) == 3

    def test_first_attempt_authentication_error_returns_400(self, client, inproc_user_headers, monkeypatch):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([stripe.error.AuthenticationError("Invalid API Key provided")])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert detail.startswith("Stripe error:"), detail
        assert "Invalid API Key" in detail, detail
        assert len(stub.calls) == 1, "must not retry after a non-InvalidRequest error"

    def test_second_attempt_card_error_returns_400(self, client, inproc_user_headers, monkeypatch):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([
            stripe.error.InvalidRequestError("managed payments unsupported", "managed_payments"),
            stripe.error.CardError("Your card was declined", "number", "card_declined"),
        ])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400, r.text
        assert "declined" in r.json()["detail"], r.text
        assert len(stub.calls) == 2

    def test_no_txn_row_when_non_invalidrequest_error_on_attempt_two(self, client, inproc_user_headers,
                                                                    monkeypatch, mongo):
        _patch_prices(monkeypatch)
        stub = _SessionCreateStub([
            stripe.error.InvalidRequestError("managed payments unsupported", "managed_payments"),
            stripe.error.RateLimitError("slow down"),
        ])
        monkeypatch.setattr(stripe.checkout.Session, "create", stub)
        before = mongo.payment_transactions.count_documents({})
        r = self._post(client, inproc_user_headers)
        assert r.status_code == 400
        assert mongo.payment_transactions.count_documents({}) == before


class TestNoLegacyMessage:
    def test_server_py_has_no_could_not_start_checkout(self):
        src = (BACKEND_DIR / "server.py").read_text()
        assert "Could not start checkout" not in src, "legacy generic message still present in server.py"
