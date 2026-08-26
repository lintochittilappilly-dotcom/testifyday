"""Edge cases: paid-plan submissions, validation, public exposure of image testimonials.

NOTE: /api/public/collection/{slug}/submit is rate limited to 5 calls / 300s per IP.
Restart the backend (`sudo supervisorctl restart backend`) before running this file
together with backend_test.py.
"""
import uuid

import pytest

from conftest import API, auth


@pytest.fixture(scope="module")
def pro_setup(api, mongo):
    """Register a user, upgrade their workspace to pro, publish a collection."""
    email = f"test_pro_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={"name": "TEST_ Pro", "email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    ws = api.get(f"{API}/workspace", headers=auth(token)).json()
    mongo.workspaces.update_one({"id": ws["id"]}, {"$set": {"plan": "pro"}})
    c = api.post(f"{API}/collections", headers=auth(token),
                 json={"name": "TEST_ Pro Page", "require_email": False})
    assert c.status_code == 200, c.text
    col = api.put(f"{API}/collections/{c.json()['id']}", headers=auth(token),
                  json={"published": True, "require_email": False}).json()
    yield {"token": token, "ws": ws, "col": col}
    mongo.testimonials.delete_many({"workspace_id": ws["id"]})


def payload(**kw):
    base = {"first_name": "TEST_Pro", "consent": True}
    base.update(kw)
    return base


class TestPaidPlanSubmit:
    def test_video_allowed_on_pro(self, api, pro_setup, reset_rate_limit):
        r = api.post(f"{API}/public/collection/{pro_setup['col']['slug']}/submit",
                     json=payload(video_url="https://example.com/v.mp4", text="loved it"))
        assert r.status_code == 200, f"pro plan video submit failed {r.status_code}: {r.text[:300]}"

    def test_image_submit_and_public_wall_exposure(self, api, pro_setup, mongo):
        slug = pro_setup["col"]["slug"]
        r = api.post(f"{API}/public/collection/{slug}/submit",
                     json=payload(first_name="TEST_WallImg", image_url="https://example.com/wall.png"))
        assert r.status_code == 200, r.text
        mongo.testimonials.update_one({"workspace_id": pro_setup["ws"]["id"], "first_name": "TEST_WallImg"},
                                      {"$set": {"status": "approved", "approved_at": "2026-01-01T00:00:00+00:00"}})
        wall = api.get(f"{API}/public/wall/{pro_setup['ws']['slug']}")
        assert wall.status_code == 200, wall.text
        item = next((t for t in wall.json()["testimonials"] if t["first_name"] == "TEST_WallImg"), None)
        assert item is not None, "approved image testimonial missing from public wall"
        # BUG EXPECTATION: image_url should be exposed publicly for image testimonials
        assert "image_url" in item and item["image_url"] == "https://example.com/wall.png", \
            f"public wall/widget payload drops image_url: {item}"


class TestSubmitValidation:
    def test_empty_content_rejected(self, api, pro_setup):
        r = api.post(f"{API}/public/collection/{pro_setup['col']['slug']}/submit", json=payload())
        assert r.status_code == 400, r.text
        assert "written" in r.json()["detail"].lower()

    def test_consent_required(self, api, pro_setup):
        r = api.post(f"{API}/public/collection/{pro_setup['col']['slug']}/submit",
                     json=payload(text="hi", consent=False))
        assert r.status_code == 400, r.text
        assert "consent" in r.json()["detail"].lower()

    def test_unknown_slug_404(self, api):
        r = api.post(f"{API}/public/collection/TEST_no_such_slug/submit", json=payload(text="hi"))
        assert r.status_code in (404, 429), r.text


class TestCaptchaEnforcement:
    def test_captcha_required_once_secret_set(self, api, admin_token, pro_setup, reset_rate_limit):
        slug = pro_setup["col"]["slug"]
        try:
            up = api.put(f"{API}/admin/settings", headers=auth(admin_token),
                         json={"recaptcha_secret_key": "TEST_dummy_secret"})
            assert up.status_code == 200, up.text
            r = api.post(f"{API}/public/collection/{slug}/submit",
                         json=payload(first_name="TEST_NoCaptcha", text="hello"))
            assert r.status_code == 400, f"expected captcha rejection, got {r.status_code}: {r.text[:200]}"
            assert "captcha" in r.json()["detail"].lower()
        finally:
            api.put(f"{API}/admin/settings", headers=auth(admin_token),
                    json={"recaptcha_secret_key": ""})
        # blank secret -> captcha bypassed (graceful fallback)
        r2 = api.post(f"{API}/public/collection/{slug}/submit",
                      json=payload(first_name="TEST_BlankSecret", text="hello again"))
        assert r2.status_code == 200, f"blank secret should bypass captcha, got {r2.status_code}: {r2.text[:200]}"
