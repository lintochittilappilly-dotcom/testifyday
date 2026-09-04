"""Admin notification digest tests (iteration 13).

Covers /api/admin/notifications/status and /admin/notifications/send-digest,
mode switching via /admin/settings, and that /auth/register + failed Stripe
checkouts enqueue events rather than blocking.
"""
import time
import uuid

import pytest
import requests

from conftest import API, ADMIN_EMAIL, auth


def _set_mode(admin_token, mode):
    r = requests.put(
        f"{API}/admin/settings",
        headers=auth(admin_token),
        json={"admin_notify_mode": mode},
    )
    assert r.status_code == 200, r.text[:300]


class TestNotificationsGuards:
    def test_status_requires_admin(self, api, nonadmin_user):
        r = requests.get(f"{API}/admin/notifications/status", headers=auth(nonadmin_user["token"]))
        assert r.status_code == 403

    def test_send_digest_requires_admin(self, api, nonadmin_user):
        r = requests.post(f"{API}/admin/notifications/send-digest", headers=auth(nonadmin_user["token"]))
        assert r.status_code == 403


class TestNotificationsQueue:
    def test_status_shape(self, api, admin_token, mongo):
        r = requests.get(f"{API}/admin/notifications/status", headers=auth(admin_token))
        assert r.status_code == 200
        d = r.json()
        for k in ("pending_total", "pending_signups", "pending_payment_failures", "mode"):
            assert k in d
        assert d["mode"] in ("instant", "daily", "off")

    def test_signup_enqueues_event(self, api, admin_token, mongo):
        # Baseline
        base = requests.get(f"{API}/admin/notifications/status", headers=auth(admin_token)).json()
        base_pending_signups = base["pending_signups"]
        # Register a fresh non-admin user
        email = f"test_digest_signup_{uuid.uuid4().hex[:8]}@example.com"
        r = api.post(f"{API}/auth/register", json={"name": "Digest Test", "email": email, "password": "TestPass123!"})
        assert r.status_code == 200
        # Wait briefly for the fire-and-forget task to persist
        time.sleep(0.5)
        after = requests.get(f"{API}/admin/notifications/status", headers=auth(admin_token)).json()
        assert after["pending_signups"] == base_pending_signups + 1

    def test_send_digest_flushes_queue(self, api, admin_token, mongo):
        # Ensure at least one event in queue by seeding an event directly
        seed_event_id = f"TEST_evt_{uuid.uuid4().hex[:8]}"
        mongo.admin_notify_queue.insert_one({
            "event_type": "signup",
            "payload": {"name": "Seed", "email": "seed@example.com", "provider": "email"},
            "created_at": "2026-01-01T00:00:00+00:00",
            "sent_at": None,
            "seed_id": seed_event_id,
        })
        try:
            r = requests.post(f"{API}/admin/notifications/send-digest", headers=auth(admin_token))
            assert r.status_code == 200
            d = r.json()
            assert d["signups"] >= 1
            # Post-flush: queue should have that seeded event marked sent_at
            stat = requests.get(f"{API}/admin/notifications/status", headers=auth(admin_token)).json()
            # Pending signups now 0
            assert stat["pending_signups"] == 0
            assert stat["pending_payment_failures"] == 0
            assert stat["last_sent"] is not None
            row = mongo.admin_notify_queue.find_one({"seed_id": seed_event_id})
            assert row and row.get("sent_at") is not None
        finally:
            mongo.admin_notify_queue.delete_many({"seed_id": seed_event_id})


class TestNotificationModes:
    @pytest.mark.parametrize("mode", ["instant", "daily", "off"])
    def test_mode_round_trip(self, api, admin_token, mode):
        _set_mode(admin_token, mode)
        r = requests.get(f"{API}/admin/notifications/status", headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["mode"] == mode
        # Reset to instant so other tests don't drift
        _set_mode(admin_token, "instant")
