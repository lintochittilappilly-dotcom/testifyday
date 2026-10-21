"""Outbound integrations: webhooks + review-request emails.

A real HTTP receiver runs in-process on the container's network address so the
backend can POST to it the same way it would to Zapier.
"""
import json
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import integrations as integ
from conftest import API, auth


# ---------- helpers ----------
def _bindable_host() -> str:
    """A non-loopback address the backend may POST to (the SSRF guard blocks 127.*).

    Prefers a routable interface such as the docker bridge; link-local 169.254.*
    and loopback are deliberately rejected by the webhook URL validator.
    """
    for host in ("172.17.0.1", "10.0.2.15"):
        sock = socket.socket()
        try:
            sock.bind((host, 0))
            return host
        except OSError:
            continue
        finally:
            sock.close()
    return "0.0.0.0"


class _Handler(BaseHTTPRequestHandler):
    received = []
    status = 200

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        type(self).received.append({"headers": dict(self.headers), "body": body, "path": self.path})
        payload = b'{"ok":true}'
        self.send_response(type(self).status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # silence the request log
        return


@pytest.fixture(scope="session")
def receiver():
    _Handler.received = []
    _Handler.status = 200
    host = _bindable_host()
    server = ThreadingHTTPServer((host, 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://{server.server_address[0]}:{server.server_address[1]}/hook"
    yield {"url": url, "handler": _Handler, "server": server}
    server.shutdown()


def _workspace(api, mongo, plan, label="int"):
    email = f"test_{label}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={"name": f"TEST_ {label}", "email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text[:300]
    token = r.json()["token"]
    ws = api.get(f"{API}/workspace", headers=auth(token)).json()
    if plan != "free":
        mongo.workspaces.update_one({"id": ws["id"]}, {"$set": {"plan": plan}})
    page = api.post(
        f"{API}/collections",
        headers=auth(token),
        json={"name": f"TEST_{label} Page", "require_email": False},
    )
    assert page.status_code == 200, page.text[:300]
    col = api.put(
        f"{API}/collections/{page.json()['id']}",
        headers=auth(token),
        json={"published": True, "allow_video": False},
    ).json()
    return {"token": token, "ws": ws, "col": col, "email": email}


@pytest.fixture(scope="module")
def pro(api, mongo):
    return _workspace(api, mongo, "pro", "pro")


@pytest.fixture(scope="module")
def free(api, mongo):
    return _workspace(api, mongo, "free", "free")


def _wait(predicate, timeout=10.0, interval=0.2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


# ---------- webhooks ----------
class TestWebhookEndpoints:
    def test_free_plan_is_rejected(self, api, free, receiver):
        r = api.post(f"{API}/webhooks", headers=auth(free["token"]), json={"url": receiver["url"]})
        assert r.status_code == 402, r.text[:300]
        assert "Pro" in r.json()["detail"]

    def test_create_hides_secret_afterwards(self, api, pro, receiver):
        created = api.post(
            f"{API}/webhooks",
            headers=auth(pro["token"]),
            json={"url": receiver["url"], "events": ["testimonial.submitted"], "description": "Zapier catch hook"},
        )
        assert created.status_code == 200, created.text[:300]
        body = created.json()
        assert body["secret"].startswith("whsec_")
        assert body["events"] == ["testimonial.submitted"]
        assert body["url"] == receiver["url"]

        listed = api.get(f"{API}/webhooks", headers=auth(pro["token"])).json()
        match = next(e for e in listed["endpoints"] if e["id"] == body["id"])
        assert "secret" not in match, "GET must not leak the signing secret"
        assert match["has_secret"] is True
        assert "testimonial.submitted" in listed["events"]

    def test_rejects_loopback_and_bad_scheme(self, api, pro):
        for url in ("http://127.0.0.1:8000/hook", "ftp://example.com/hook", "not-a-url"):
            r = api.post(f"{API}/webhooks", headers=auth(pro["token"]), json={"url": url})
            assert r.status_code == 400, f"{url} should be rejected, got {r.status_code}"

    def test_unknown_event_rejected(self, api, pro, receiver):
        r = api.post(
            f"{API}/webhooks",
            headers=auth(pro["token"]),
            json={"url": receiver["url"], "events": ["testimonial.teleported"]},
        )
        assert r.status_code == 400, r.text[:300]


class TestWebhookDelivery:
    def test_test_endpoint_signs_and_delivers(self, api, pro, receiver):
        receiver["handler"].received.clear()
        receiver["handler"].status = 200
        created = api.post(
            f"{API}/webhooks", headers=auth(pro["token"]), json={"url": receiver["url"], "events": ["*"]}
        ).json()
        r = api.post(f"{API}/webhooks/{created['id']}/test", headers=auth(pro["token"]))
        assert r.status_code == 200, r.text[:300]
        assert r.json()["ok"] is True, r.json()

        assert _wait(lambda: receiver["handler"].received), "receiver never got a POST"
        got = receiver["handler"].received[-1]
        headers, body = got["headers"], got["body"]
        assert headers["X-Testify-Event"] == "testimonial.submitted"
        expected = integ.sign_payload(created["secret"], headers["X-Testify-Timestamp"], body)
        assert headers["X-Testify-Signature"] == expected, "signature does not match the documented scheme"

        payload = json.loads(body)
        assert payload["event"] == "testimonial.submitted"
        assert payload["data"]["test"] is True

    def test_500_response_is_retried_with_backoff(self, api, pro, receiver, mongo):
        receiver["handler"].status = 500
        created = api.post(
            f"{API}/webhooks", headers=auth(pro["token"]), json={"url": receiver["url"], "events": ["*"]}
        ).json()
        r = api.post(f"{API}/webhooks/{created['id']}/test", headers=auth(pro["token"]))
        assert r.status_code == 200
        assert r.json()["ok"] is False
        assert r.json()["response_status"] == 500

        deliveries = api.get(f"{API}/webhooks/{created['id']}/deliveries", headers=auth(pro["token"])).json()
        assert deliveries, "delivery should be recorded"
        row = deliveries[0]
        assert row["status"] in ("retrying", "failed")
        assert row["attempts"] == 1
        assert row["next_attempt_at"], "a failed delivery must be scheduled for retry"
        receiver["handler"].status = 200

    def test_approval_emits_approved_event(self, api, pro, receiver, mongo):
        receiver["handler"].received.clear()
        receiver["handler"].status = 200
        created = api.post(
            f"{API}/webhooks", headers=auth(pro["token"]), json={"url": receiver["url"], "events": ["testimonial.approved"]}
        ).json()
        doc = {
            "id": f"tst_wh_{uuid.uuid4().hex[:6]}",
            "workspace_id": pro["ws"]["id"],
            "collection_id": pro["col"]["id"],
            "first_name": "TEST_Webhook",
            "last_name": "",
            "email": "",
            "text": "Great",
            "status": "pending",
            "featured": False,
            "tags": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        mongo.testimonials.insert_one(doc)
        r = api.post(f"{API}/testimonials/{doc['id']}/status", headers=auth(pro["token"]), json={"status": "approved"})
        assert r.status_code == 200, r.text[:300]

        got = _wait(lambda: next((x for x in receiver["handler"].received if "testimonial.approved" in x["headers"]["X-Testify-Event"]), None))
        assert got, f"no approved event delivered; saw {[x['headers'].get('X-Testify-Event') for x in receiver['handler'].received]}"
        assert json.loads(got["body"])["data"]["testimonial"]["id"] == doc["id"]

        listing = api.get(f"{API}/webhooks/{created['id']}/deliveries", headers=auth(pro["token"])).json()
        assert any(d["event"] == "testimonial.approved" for d in listing)


# ---------- review-request emails ----------
class TestRequestEmails:
    def _create(self, api, ws, emails, **extra):
        body = {"collection_id": ws["col"]["id"], "emails": emails, **extra}
        return api.post(f"{API}/request-emails", headers=auth(ws["token"]), json=body)

    def test_campaign_sends_and_records_recipients(self, api, pro):
        emails = [f"TEST_req{i}_{uuid.uuid4().hex[:5]}@example.com" for i in range(3)]
        r = self._create(api, pro, emails, subject="Quick favour", message="Would you leave us a line?")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["queued"] == 3
        campaign_id = body["campaign"]["id"]

        done = _wait(
            lambda: (
                lambda detail: detail
                if detail["status"] == "completed"
                else None
            )(api.get(f"{API}/request-emails/{campaign_id}", headers=auth(pro["token"])).json())
        )
        assert done, "campaign never completed"
        assert done["sent_count"] == 3, done
        statuses = {r["status"] for r in done["recipients"]}
        assert statuses == {"sent"}, statuses

    def test_invalid_and_duplicate_addresses_are_reported(self, api, pro, mongo):
        mongo.testimonials.insert_one({
            "id": f"tst_dup_{uuid.uuid4().hex[:5]}", "workspace_id": pro["ws"]["id"],
            "collection_id": pro["col"]["id"], "first_name": "TEST_Dup", "last_name": "",
            "email": "already@example.com", "text": "hi", "status": "approved", "featured": False,
            "tags": [], "created_at": "2026-01-01T00:00:00+00:00",
        })
        r = self._create(api, pro, ["already@example.com", "not-an-email", "fresh@example.com"])
        assert r.status_code == 200, r.text[:300]
        skipped = r.json()["skipped"]
        assert "already@example.com" in skipped["already_testimonial"]
        assert "not-an-email" in skipped["invalid"]
        assert r.json()["queued"] == 1

    def test_unpublished_collection_rejected(self, api, pro):
        page = api.post(f"{API}/collections", headers=auth(pro["token"]), json={"name": "TEST_ Draft"})
        r = api.post(
            f"{API}/request-emails",
            headers=auth(pro["token"]),
            json={"collection_id": page.json()["id"], "emails": ["someone@example.com"]},
        )
        assert r.status_code == 400, r.text[:300]
        assert "Publish" in r.json()["detail"]

    def test_free_plan_quota_is_25(self, api, free, mongo):
        # Burn the free quota with sent rows, then expect a 402.
        mongo.request_campaigns.insert_one({
            "id": f"req_burn_{uuid.uuid4().hex[:5]}",
            "workspace_id": free["ws"]["id"],
            "collection_id": free["col"]["id"],
            "status": "completed",
            "created_at": "2099-01-01T00:00:00+00:00",
            "recipients": [{"email": f"burn{i}@example.com", "status": "sent"} for i in range(25)],
        })
        r = self._create(api, free, ["one-more@example.com"])
        assert r.status_code == 402, r.text[:300]
        assert "25" in r.json()["detail"]

        usage = api.get(f"{API}/request-emails", headers=auth(free["token"])).json()["usage"]
        assert usage["limit_30d"] == 25
        assert usage["sent_30d"] >= 25

    def test_retry_requeues_failed_recipients(self, api, pro, mongo):
        cid = f"req_retry_{uuid.uuid4().hex[:5]}"
        mongo.request_campaigns.insert_one({
            "id": cid, "workspace_id": pro["ws"]["id"], "collection_id": pro["col"]["id"],
            "status": "completed", "created_at": "2026-01-01T00:00:00+00:00",
            "recipients": [{"email": "retry@example.com", "status": "failed", "sent_at": None, "error": "boom"}],
        })
        r = api.post(f"{API}/request-emails/{cid}/retry", headers=auth(pro["token"]))
        assert r.status_code == 200, r.text[:300]
        assert r.json()["retried"] == 1
