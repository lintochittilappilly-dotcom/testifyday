"""Iteration 10 — per-plan video testimonial limits with admin overrides.

Covers:
  * settings_store: video_limits key in GET/PUT /api/admin/settings (merge behaviour)
  * server._public_collection: video_max_duration_sec / max_size_mb / min_duration_sec per plan
  * /api/upload 413 size caps (image 5MB, video)
  * submit_testimonial video max_count cap (0 = unlimited)
"""
import uuid

import pytest

from conftest import API, auth


# ---------- helpers / fixtures ----------

def _make_workspace(api, mongo, plan, label):
    email = f"test_vl{label}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={"name": f"TEST_ {label}", "email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    ws = api.get(f"{API}/workspace", headers=auth(token)).json()
    if plan != "free":
        mongo.workspaces.update_one({"id": ws["id"]}, {"$set": {"plan": plan}})
    c = api.post(f"{API}/collections", headers=auth(token),
                 json={"name": f"TEST_ {label} Page", "require_email": False})
    assert c.status_code == 200, c.text
    col = api.put(f"{API}/collections/{c.json()['id']}", headers=auth(token),
                  json={"published": True, "require_email": False, "allow_video": True}).json()
    return {"token": token, "ws": ws, "col": col}


@pytest.fixture(scope="module")
def pro_ws(api, mongo):
    s = _make_workspace(api, mongo, "pro", "pro")
    yield s
    mongo.testimonials.delete_many({"workspace_id": s["ws"]["id"]})


@pytest.fixture(scope="module")
def business_ws(api, mongo):
    s = _make_workspace(api, mongo, "business", "biz")
    yield s
    mongo.testimonials.delete_many({"workspace_id": s["ws"]["id"]})


@pytest.fixture(scope="module")
def free_ws(api, mongo):
    s = _make_workspace(api, mongo, "free", "free")
    yield s
    mongo.testimonials.delete_many({"workspace_id": s["ws"]["id"]})


@pytest.fixture
def reset_video_limits(api, admin_token):
    """Always clear the admin override after a test that sets one."""
    yield
    r = api.put(f"{API}/admin/settings", headers=auth(admin_token), json={"video_limits": {}})
    assert r.status_code == 200, r.text


def _payload(**kw):
    base = {"first_name": "TEST_VL", "consent": True}
    base.update(kw)
    return base


# ---------- 1. admin settings key ----------

class TestAdminVideoLimitsSetting:
    def test_get_settings_exposes_video_limits_key(self, api, admin_token):
        r = api.get(f"{API}/admin/settings", headers=auth(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert "video_limits" in body, f"video_limits missing from settings payload: {list(body)}"
        assert isinstance(body["video_limits"], dict)

    def test_put_and_get_merge(self, api, admin_token, reset_video_limits):
        override = {"min_duration_sec": 15, "pro": {"max_duration_sec": 90, "max_size_mb": 75, "max_count": 20}}
        r = api.put(f"{API}/admin/settings", headers=auth(admin_token), json={"video_limits": override})
        assert r.status_code == 200, r.text
        assert r.json()["video_limits"] == override

        g = api.get(f"{API}/admin/settings", headers=auth(admin_token)).json()
        assert g["video_limits"]["min_duration_sec"] == 15
        assert g["video_limits"]["pro"] == {"max_duration_sec": 90, "max_size_mb": 75, "max_count": 20}

    def test_other_settings_not_wiped_by_video_limits_put(self, api, admin_token, reset_video_limits):
        before = api.get(f"{API}/admin/settings", headers=auth(admin_token)).json()
        api.put(f"{API}/admin/settings", headers=auth(admin_token), json={"video_limits": {"min_duration_sec": 12}})
        after = api.get(f"{API}/admin/settings", headers=auth(admin_token)).json()
        for k in ("sender_email", "promo_banner", "checkout_coupon_id"):
            assert after[k] == before[k], f"{k} changed after video_limits-only PUT"

    def test_requires_admin(self, api, nonadmin_user):
        r = api.put(f"{API}/admin/settings", headers=auth(nonadmin_user["token"]),
                    json={"video_limits": {"min_duration_sec": 99}})
        assert r.status_code in (401, 403), r.text


# ---------- 2/3. public collection defaults per plan ----------

class TestPublicCollectionVideoLimits:
    def test_business_defaults(self, api, business_ws):
        r = api.get(f"{API}/public/collection/{business_ws['col']['slug']}")
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["allow_video"] is True
        assert b["video_max_duration_sec"] == 180, b
        assert b["video_max_size_mb"] == 200, b
        assert b["video_min_duration_sec"] == 10, b

    def test_pro_defaults(self, api, pro_ws):
        b = api.get(f"{API}/public/collection/{pro_ws['col']['slug']}").json()
        assert b["allow_video"] is True
        assert b["video_max_duration_sec"] == 60, b
        assert b["video_max_size_mb"] == 50, b
        assert b["video_min_duration_sec"] == 10, b

    def test_free_plan_no_video(self, api, free_ws):
        b = api.get(f"{API}/public/collection/{free_ws['col']['slug']}").json()
        assert b["allow_video"] is False, b
        assert b["video_max_duration_sec"] is None, b
        assert b["video_max_size_mb"] is None, b
        assert b["video_min_duration_sec"] is None, b


# ---------- 4. admin override reflected publicly ----------

class TestOverrideAffectsPublicCollection:
    def test_pro_duration_override(self, api, admin_token, pro_ws, business_ws, reset_video_limits):
        r = api.put(f"{API}/admin/settings", headers=auth(admin_token),
                    json={"video_limits": {"pro": {"max_duration_sec": 90}}})
        assert r.status_code == 200, r.text
        b = api.get(f"{API}/public/collection/{pro_ws['col']['slug']}").json()
        assert b["video_max_duration_sec"] == 90, b
        # untouched keys fall back to defaults
        assert b["video_max_size_mb"] == 50, b
        # business unaffected
        biz = api.get(f"{API}/public/collection/{business_ws['col']['slug']}").json()
        assert biz["video_max_duration_sec"] == 180, biz

    def test_min_duration_override(self, api, admin_token, pro_ws, reset_video_limits):
        api.put(f"{API}/admin/settings", headers=auth(admin_token),
                json={"video_limits": {"min_duration_sec": 15}})
        b = api.get(f"{API}/public/collection/{pro_ws['col']['slug']}").json()
        assert b["video_min_duration_sec"] == 15, b

    def test_reset_restores_defaults(self, api, admin_token, pro_ws):
        api.put(f"{API}/admin/settings", headers=auth(admin_token), json={"video_limits": {}})
        b = api.get(f"{API}/public/collection/{pro_ws['col']['slug']}").json()
        assert b["video_max_duration_sec"] == 60, b
        assert b["video_min_duration_sec"] == 10, b


# ---------- 5. upload size caps ----------

class TestUploadSizeCaps:
    """The session-scoped `api` fixture forces Content-Type: application/json,
    so multipart uploads use a bare requests call."""

    @staticmethod
    def _upload(filename, blob, ct):
        import requests
        return requests.post(f"{API}/upload", files={"file": (filename, blob, ct)}, timeout=180)

    def test_png_over_5mb_rejected(self):
        blob = b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024)
        r = self._upload("TEST_big.png", blob, "image/png")
        assert r.status_code == 413, f"expected 413, got {r.status_code}: {r.text[:200]}"
        assert r.json()["detail"] == "Image is too large. Max 5MB.", r.text

    def test_unsupported_type_rejected(self):
        r = self._upload("TEST_x.exe", b"0" * 1024, "application/x-msdownload")
        assert r.status_code == 400, r.text
        assert "unsupported" in r.json()["detail"].lower()

    def test_video_under_business_cap_passes_size_gate(self):
        """8MB webm — well under business max_size_mb=200 -> must NOT be size-rejected.

        This env has no S3_BUCKET_NAME so the storage layer answers 500; the assertion
        is that the size gate does not fire. The 80MB/100MB/210MB/500MB cases are
        covered in-process in tests/test_upload_size_caps.py (python-multipart takes
        minutes to parse a 100MB+ multipart body, so they cannot run over HTTP).
        """
        blob = b"0" * (8 * 1024 * 1024)
        r = self._upload("TEST_8mb.webm", blob, "video/webm")
        assert r.status_code != 413, f"8MB video must pass the size gate: {r.text[:200]}"

    def test_video_over_overridden_cap_rejected_over_http(self, api, admin_token, reset_video_limits):
        """Lower the business cap to 1MB via admin PUT, then a 2MB video -> 413 with
        the per-plan message (proves the per-plan cap is wired into the HTTP path)."""
        s = api.put(f"{API}/admin/settings", headers=auth(admin_token),
                    json={"video_limits": {"pro": {"max_size_mb": 1}, "business": {"max_size_mb": 1}}})
        assert s.status_code == 200, s.text
        blob = b"0" * (2 * 1024 * 1024)
        r = self._upload("TEST_2mb.webm", blob, "video/webm")
        assert r.status_code == 413, f"expected 413, got {r.status_code}: {r.text[:200]}"
        assert r.json()["detail"] == "Video is too large. Max 1MB.", r.text


# ---------- 6/7. submit video count cap ----------

class TestVideoCountCap:
    def _seed_videos(self, mongo, ws_id, col_id, n):
        docs = [{
            "id": f"tst_TESTVL{uuid.uuid4().hex[:10]}",
            "workspace_id": ws_id,
            "collection_id": col_id,
            "first_name": "TEST_Seed",
            "last_name": "",
            "email": "",
            "company": "",
            "role": "",
            "website": "",
            "text": "seeded",
            "image_url": None,
            "video_url": "https://example.com/seed.mp4",
            "video_thumbnail_url": None,
            "rating": 5,
            "status": "approved",
            "featured": False,
            "consent": True,
            "source": "collection",
            "created_at": "2026-01-01T00:00:00+00:00",
        } for _ in range(n)]
        mongo.testimonials.insert_many(docs)

    def test_pro_capped_at_100_videos(self, api, mongo, pro_ws, reset_rate_limit):
        mongo.testimonials.delete_many({"workspace_id": pro_ws["ws"]["id"]})
        self._seed_videos(mongo, pro_ws["ws"]["id"], pro_ws["col"]["id"], 100)
        r = api.post(f"{API}/public/collection/{pro_ws['col']['slug']}/submit",
                     json=_payload(video_url="https://example.com/new.mp4", text="capped?"))
        assert r.status_code == 402, f"expected 402 video cap, got {r.status_code}: {r.text[:300]}"
        assert "plan limit of 100 video testimonials" in r.json()["detail"], r.text

    def test_pro_allows_31st_video(self, api, mongo, pro_ws, reset_rate_limit):
        """Pro used to hard-stop at 30 videos, two steps above the $29 price point."""
        mongo.testimonials.delete_many({"workspace_id": pro_ws["ws"]["id"]})
        self._seed_videos(mongo, pro_ws["ws"]["id"], pro_ws["col"]["id"], 30)
        r = api.post(f"{API}/public/collection/{pro_ws['col']['slug']}/submit",
                     json=_payload(first_name="TEST_Pro31", video_url="https://example.com/31.mp4"))
        assert r.status_code == 200, f"Pro must accept a 31st video: {r.status_code} {r.text[:300]}"

    def test_pro_text_submit_still_allowed_at_video_cap(self, api, pro_ws):
        r = api.post(f"{API}/public/collection/{pro_ws['col']['slug']}/submit",
                     json=_payload(first_name="TEST_TextOK", text="text only should pass"))
        assert r.status_code == 200, f"text testimonial blocked by video cap: {r.status_code} {r.text[:300]}"

    def test_pro_cap_respects_admin_override(self, api, mongo, admin_token, pro_ws, reset_video_limits):
        api.put(f"{API}/admin/settings", headers=auth(admin_token),
                json={"video_limits": {"pro": {"max_count": 5}}})
        mongo.testimonials.delete_many({"workspace_id": pro_ws["ws"]["id"]})
        self._seed_videos(mongo, pro_ws["ws"]["id"], pro_ws["col"]["id"], 5)
        r = api.post(f"{API}/public/collection/{pro_ws['col']['slug']}/submit",
                     json=_payload(first_name="TEST_Override", video_url="https://example.com/o.mp4"))
        assert r.status_code == 402, f"override max_count=5 should block the 6th video: {r.status_code} {r.text[:300]}"
        assert "plan limit of 5 video testimonials" in r.json()["detail"], r.text

    def test_business_unlimited_videos(self, api, mongo, business_ws, reset_rate_limit):
        mongo.testimonials.delete_many({"workspace_id": business_ws["ws"]["id"]})
        self._seed_videos(mongo, business_ws["ws"]["id"], business_ws["col"]["id"], 35)
        r = api.post(f"{API}/public/collection/{business_ws['col']['slug']}/submit",
                     json=_payload(first_name="TEST_BizVid", video_url="https://example.com/b.mp4"))
        assert r.status_code == 200, f"business max_count=0 should be unlimited: {r.status_code} {r.text[:300]}"

    def test_free_plan_video_still_blocked(self, api, free_ws):
        r = api.post(f"{API}/public/collection/{free_ws['col']['slug']}/submit",
                     json=_payload(first_name="TEST_FreeVid", video_url="https://example.com/f.mp4"))
        assert r.status_code == 402, r.text
        assert "paid feature" in r.json()["detail"].lower(), r.text
