"""Iteration 2 retest: the four defects reported in /app/test_reports/iteration_1.json.

1. image_url exposed by /api/public/wall/{ws_slug} and /api/public/widget/{wid}
2. allow_video on /api/public/collection/{slug} gated by workspace plan
3. GET /api/health available through the /api prefix
4. (see test_admin_failclosed.py) ADMIN_EMAIL unset -> nobody is admin
"""
import uuid

import pytest
import requests

from conftest import API, auth


# ---------- module fixtures ----------
def _register(api, prefix):
    email = f"test_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={"name": "TEST_ It2", "email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _make_collection(api, token, name, allow_video=True):
    c = api.post(f"{API}/collections", headers=auth(token),
                 json={"name": name, "require_email": False})
    assert c.status_code == 200, c.text
    col = api.put(f"{API}/collections/{c.json()['id']}", headers=auth(token),
                  json={"published": True, "require_email": False, "allow_video": allow_video}).json()
    return col


@pytest.fixture(scope="module")
def free_ws(api, mongo):
    token = _register(api, "it2free")
    ws = api.get(f"{API}/workspace", headers=auth(token)).json()
    assert ws.get("plan", "free") == "free"
    col = _make_collection(api, token, "TEST_ It2 Free Page", allow_video=True)
    yield {"token": token, "ws": ws, "col": col}
    mongo.testimonials.delete_many({"workspace_id": ws["id"]})


@pytest.fixture(scope="module")
def pro_ws(api, mongo):
    token = _register(api, "it2pro")
    ws = api.get(f"{API}/workspace", headers=auth(token)).json()
    mongo.workspaces.update_one({"id": ws["id"]}, {"$set": {"plan": "pro"}})
    col = _make_collection(api, token, "TEST_ It2 Pro Page", allow_video=True)
    yield {"token": token, "ws": ws, "col": col}
    mongo.testimonials.delete_many({"workspace_id": ws["id"]})


def payload(**kw):
    base = {"first_name": "TEST_It2", "consent": True}
    base.update(kw)
    return base


# ---------- fix 3: /api/health ----------
class TestHealth:
    def test_api_health(self, api):
        r = api.get(f"{API}/health")
        assert r.status_code == 200, f"GET /api/health -> {r.status_code}: {r.text[:200]}"
        assert r.json() == {"status": "ok"}, r.text

    def test_root_health_still_works(self, api):
        from conftest import BASE_URL
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ok"


# ---------- fix 2: allow_video plan gating on the public collection payload ----------
class TestPublicCollectionVideoGating:
    def test_free_plan_forces_allow_video_false(self, api, free_ws, mongo):
        # collection itself has allow_video=True
        stored = mongo.collections.find_one({"id": free_ws["col"]["id"]}, {"_id": 0, "allow_video": 1})
        assert stored.get("allow_video") is True, f"precondition: collection allow_video must be True, got {stored}"
        r = api.get(f"{API}/public/collection/{free_ws['col']['slug']}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["allow_video"] is False, \
            f"Free plan must expose allow_video=false, got {body['allow_video']}"
        assert body["allow_text"] is True

    def test_pro_plan_keeps_allow_video_true(self, api, pro_ws):
        r = api.get(f"{API}/public/collection/{pro_ws['col']['slug']}")
        assert r.status_code == 200, r.text
        assert r.json()["allow_video"] is True, "Pro plan with allow_video=true must expose allow_video=true"

    def test_pro_plan_respects_collection_allow_video_false(self, api, pro_ws, mongo):
        mongo.collections.update_one({"id": pro_ws["col"]["id"]}, {"$set": {"allow_video": False}})
        try:
            r = api.get(f"{API}/public/collection/{pro_ws['col']['slug']}")
            assert r.status_code == 200, r.text
            assert r.json()["allow_video"] is False, "collection-level allow_video=false must win on Pro too"
        finally:
            mongo.collections.update_one({"id": pro_ws["col"]["id"]}, {"$set": {"allow_video": True}})

    def test_business_plan_keeps_allow_video_true(self, api, pro_ws, mongo):
        mongo.workspaces.update_one({"id": pro_ws["ws"]["id"]}, {"$set": {"plan": "business"}})
        try:
            r = api.get(f"{API}/public/collection/{pro_ws['col']['slug']}")
            assert r.status_code == 200, r.text
            assert r.json()["allow_video"] is True, "business plan must expose allow_video=true"
        finally:
            mongo.workspaces.update_one({"id": pro_ws["ws"]["id"]}, {"$set": {"plan": "pro"}})


# ---------- fix 1: image_url in public payloads ----------
class TestPublicImageUrlExposure:
    IMG = "https://example.com/it2-free-image.png"

    def test_image_only_submit_on_free_plan_then_wall_and_widget(self, api, free_ws, mongo, reset_rate_limit):
        slug = free_ws["col"]["slug"]
        r = api.post(f"{API}/public/collection/{slug}/submit",
                     json=payload(first_name="TEST_It2FreeImg", image_url=self.IMG))
        assert r.status_code == 200, f"image-only submit on free plan failed {r.status_code}: {r.text[:300]}"

        upd = mongo.testimonials.update_one(
            {"workspace_id": free_ws["ws"]["id"], "first_name": "TEST_It2FreeImg"},
            {"$set": {"status": "approved", "approved_at": "2026-01-01T00:00:00+00:00"}})
        assert upd.matched_count == 1, "submitted testimonial was not persisted"

        # ---- public wall ----
        wall = api.get(f"{API}/public/wall/{free_ws['ws']['slug']}")
        assert wall.status_code == 200, wall.text
        item = next((t for t in wall.json()["testimonials"] if t["first_name"] == "TEST_It2FreeImg"), None)
        assert item is not None, "approved image testimonial missing from public wall"
        assert item.get("image_url") == self.IMG, f"wall payload image_url wrong: {item}"
        assert "_id" not in item

        # ---- public widget (source=approved) ----
        w = api.post(f"{API}/widgets", headers=auth(free_ws["token"]),
                     json={"name": "TEST_ It2 Widget", "type": "grid",
                           "configuration": {"source": "approved", "limit": 9}})
        assert w.status_code == 200, f"widget create failed {w.status_code}: {w.text[:300]}"
        wid = w.json()["id"]
        pw = api.get(f"{API}/public/widget/{wid}")
        assert pw.status_code == 200, pw.text
        witem = next((t for t in pw.json()["testimonials"] if t["first_name"] == "TEST_It2FreeImg"), None)
        assert witem is not None, "approved image testimonial missing from widget payload"
        assert witem.get("image_url") == self.IMG, f"widget payload image_url wrong: {witem}"
        assert "_id" not in witem
