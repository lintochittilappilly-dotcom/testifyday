"""Testify backend regression + iteration tests.

Modules covered:
  - /api/plans (admin editable plans/pricing)
  - /api/admin/settings (coupon, promo banner, plans_override, RBAC)
  - /api/public/config (recaptcha site key + promo banner)
  - /api/public/collection/{slug}/submit (free plan limits, image testimonials)
  - auth + collections + testimonials regression

NOTE: the submit endpoint is rate limited to 5 calls / 300s per client IP.
This suite makes exactly 4 submit calls. Restart the backend before re-running
to reset the in-memory rate limiter.
"""
import pytest

from conftest import API, auth, ADMIN_EMAIL


# ---------------- module: /api/plans defaults ----------------
class TestPlansDefaults:
    def test_plans_defaults(self, api):
        r = api.get(f"{API}/plans")
        assert r.status_code == 200, r.text
        plans = r.json()
        assert isinstance(plans, list) and len(plans) == 3
        by_id = {p["id"]: p for p in plans}
        assert set(by_id) == {"free", "pro", "business"}
        assert by_id["free"]["price_monthly"] == 0
        assert by_id["pro"]["price_monthly"] == 29
        assert by_id["business"]["price_monthly"] == 79
        assert "Up to 10 testimonials" in by_id["free"]["features"]
        assert "Unlimited widgets" in by_id["free"]["features"]
        assert any("image" in f.lower() for f in by_id["free"]["features"])
        assert by_id["pro"]["lookup_monthly"] == "pro_monthly"
        assert by_id["business"]["lookup_yearly"] == "business_yearly"
        assert by_id["pro"].get("featured") is True


# ---------------- module: /api/admin/settings ----------------
class TestAdminSettings:
    def test_non_admin_get_forbidden(self, api, nonadmin_user):
        r = api.get(f"{API}/admin/settings", headers=auth(nonadmin_user["token"]))
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    def test_non_admin_put_forbidden(self, api, nonadmin_user):
        r = api.put(f"{API}/admin/settings", headers=auth(nonadmin_user["token"]),
                    json={"promo_banner": "HACKED"})
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    def test_unauthenticated_rejected(self, api):
        r = api.get(f"{API}/admin/settings")
        assert r.status_code == 401

    def test_admin_update_and_persist(self, api, admin_token):
        payload = {
            "checkout_coupon_id": "TEST_COUPON_50",
            "promo_banner": "TEST_ Summer sale - 50% off",
            "plans_override": [{"id": "pro", "price_monthly": 99, "price_yearly": 990,
                                "cta": "TEST_ Get Pro", "features": ["A", "B"]}],
        }
        r = api.put(f"{API}/admin/settings", headers=auth(admin_token), json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["checkout_coupon_id"] == "TEST_COUPON_50"
        assert body["promo_banner"] == "TEST_ Summer sale - 50% off"
        assert body["plans_override"][0]["price_monthly"] == 99
        assert "_id" not in body

        g = api.get(f"{API}/admin/settings", headers=auth(admin_token))
        assert g.status_code == 200, g.text
        s = g.json()
        assert s["checkout_coupon_id"] == "TEST_COUPON_50"
        assert s["promo_banner"] == "TEST_ Summer sale - 50% off"
        assert s["plans_override"][0]["cta"] == "TEST_ Get Pro"
        assert "google_places_configured" in s

    def test_plans_reflect_override(self, api, admin_token):
        r = api.get(f"{API}/plans")
        assert r.status_code == 200
        pro = {p["id"]: p for p in r.json()}["pro"]
        assert pro["price_monthly"] == 99, f"override not applied: {pro}"
        assert pro["price_yearly"] == 990
        assert pro["cta"] == "TEST_ Get Pro"
        assert pro["features"] == ["A", "B"]
        # untouched plans keep defaults
        free = {p["id"]: p for p in r.json()}["free"]
        assert free["price_monthly"] == 0

    def test_public_config_returns_banner(self, api):
        r = api.get(f"{API}/public/config")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "recaptcha_site_key" in body
        assert body["promo_banner"] == "TEST_ Summer sale - 50% off"

    def test_reset_override_restores_defaults(self, api, admin_token):
        r = api.put(f"{API}/admin/settings", headers=auth(admin_token),
                    json={"plans_override": [], "promo_banner": "", "checkout_coupon_id": ""})
        assert r.status_code == 200, r.text
        pro = {p["id"]: p for p in api.get(f"{API}/plans").json()}["pro"]
        assert pro["price_monthly"] == 29
        cfg = api.get(f"{API}/public/config").json()
        assert cfg["promo_banner"] == ""


# ---------------- module: auth regression ----------------
class TestAuthRegression:
    def test_me(self, api, free_user):
        r = api.get(f"{API}/auth/me", headers=auth(free_user["token"]))
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["email"] == free_user["email"]
        assert me["is_admin"] is False
        assert "password_hash" not in me

    def test_login(self, api, free_user):
        r = api.post(f"{API}/auth/login",
                     json={"email": free_user["email"], "password": free_user["password"]})
        assert r.status_code == 200, r.text
        assert r.json()["user"]["email"] == free_user["email"]

    def test_login_wrong_password(self, api, free_user):
        r = api.post(f"{API}/auth/login", json={"email": free_user["email"], "password": "wrong-pass"})
        assert r.status_code == 401

    def test_duplicate_register(self, api, free_user):
        r = api.post(f"{API}/auth/register",
                     json={"name": "dup", "email": free_user["email"], "password": "TestPass123!"})
        assert r.status_code == 400

    def test_admin_flag(self, api, admin_token):
        r = api.get(f"{API}/auth/me", headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL.lower()
        assert r.json()["is_admin"] is True


# ---------------- module: free plan collection + submit ----------------
@pytest.fixture(scope="class")
def free_collection(api, free_user, mongo):
    """Publish a collection on the free-plan workspace under test."""
    ws = api.get(f"{API}/workspace", headers=auth(free_user["token"])).json()
    assert ws.get("plan") == "free", f"new workspace should default to free plan, got {ws.get('plan')}"
    cols = api.get(f"{API}/collections", headers=auth(free_user["token"])).json()
    if cols:
        col = cols[0]
    else:
        r = api.post(f"{API}/collections", headers=auth(free_user["token"]),
                     json={"name": "TEST_ Testify Build", "require_email": False})
        assert r.status_code == 200, r.text
        col = r.json()
    up = api.put(f"{API}/collections/{col['id']}", headers=auth(free_user["token"]),
                 json={"published": True, "require_email": False})
    assert up.status_code == 200, up.text
    col = up.json()
    yield {"ws": ws, "col": col}
    mongo.testimonials.delete_many({"workspace_id": ws["id"]})


class TestFreePlanSubmit:
    def _payload(self, **kw):
        base = {"first_name": "TEST_Jane", "last_name": "Doe", "consent": True, "rating": 5}
        base.update(kw)
        return base

    def test_public_collection_visible(self, api, free_collection):
        r = api.get(f"{API}/public/collection/{free_collection['col']['slug']}")
        assert r.status_code == 200, r.text

    def test_video_rejected_on_free(self, api, free_collection, reset_rate_limit):
        slug = free_collection["col"]["slug"]
        r = api.post(f"{API}/public/collection/{slug}/submit",
                     json=self._payload(video_url="https://example.com/v.mp4"))
        assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text[:300]}"
        assert "video" in r.json()["detail"].lower()

    def test_image_only_accepted(self, api, free_collection, mongo):
        slug = free_collection["col"]["slug"]
        r = api.post(f"{API}/public/collection/{slug}/submit",
                     json=self._payload(first_name="TEST_Img", image_url="https://example.com/i.png"))
        assert r.status_code == 200, f"image-only submit failed {r.status_code}: {r.text[:300]}"
        assert r.json()["ok"] is True
        doc = mongo.testimonials.find_one({"workspace_id": free_collection["ws"]["id"],
                                           "first_name": "TEST_Img"})
        assert doc is not None, "image testimonial not persisted"
        assert doc["image_url"] == "https://example.com/i.png"
        assert doc["status"] == "pending"

    def test_text_only_accepted(self, api, free_collection, mongo):
        slug = free_collection["col"]["slug"]
        r = api.post(f"{API}/public/collection/{slug}/submit",
                     json=self._payload(first_name="TEST_Txt", text="Great product, loved it!"))
        assert r.status_code == 200, f"text submit failed {r.status_code}: {r.text[:300]}"
        doc = mongo.testimonials.find_one({"workspace_id": free_collection["ws"]["id"],
                                           "first_name": "TEST_Txt"})
        assert doc is not None and doc["text"] == "Great product, loved it!"

    def test_free_limit_ten_enforced(self, api, free_collection, mongo):
        ws_id = free_collection["ws"]["id"]
        col = free_collection["col"]
        existing = mongo.testimonials.count_documents({"workspace_id": ws_id})
        filler = []
        for i in range(max(0, 10 - existing)):
            filler.append({
                "id": f"tst_TESTfill{i}", "workspace_id": ws_id, "collection_id": col["id"],
                "first_name": f"TEST_Fill{i}", "last_name": "", "email": "", "text": "filler",
                "status": "pending", "featured": False, "tags": [], "submitted_at": "2026-01-01T00:00:00+00:00",
            })
        if filler:
            mongo.testimonials.insert_many(filler)
        assert mongo.testimonials.count_documents({"workspace_id": ws_id}) >= 10
        r = api.post(f"{API}/public/collection/{col['slug']}/submit",
                     json=self._payload(first_name="TEST_Eleventh", text="eleventh one"))
        assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text[:300]}"
        assert "10 testimonials" in r.json()["detail"]

    def test_free_plan_allows_extra_collections_and_widgets(self, api, free_user, free_collection):
        """Collections and widgets are unlimited on Free — only testimonials are capped."""
        r = api.post(f"{API}/collections", headers=auth(free_user["token"]),
                     json={"name": "TEST_ Second page"})
        assert r.status_code == 200, f"second collection should be allowed: {r.status_code} {r.text[:200]}"
        c2 = r.json()
        w1 = api.post(f"{API}/widgets", headers=auth(free_user["token"]),
                      json={"name": "TEST_W1", "type": "grid", "configuration": {}})
        assert w1.status_code == 200, f"first widget failed: {w1.status_code} {w1.text[:200]}"
        w2 = api.post(f"{API}/widgets", headers=auth(free_user["token"]),
                      json={"name": "TEST_W2", "type": "carousel", "configuration": {}})
        assert w2.status_code == 200, f"second widget should be allowed: {w2.status_code} {w2.text[:200]}"
        cols = api.get(f"{API}/collections", headers=auth(free_user["token"])).json()
        assert any(c["id"] == c2["id"] for c in cols), "second collection missing from list"
        wids = [w["id"] for w in api.get(f"{API}/widgets", headers=auth(free_user["token"])).json()]
        assert w1.json()["id"] in wids and w2.json()["id"] in wids, "widgets missing from list"

    def test_list_testimonials(self, api, free_user):
        r = api.get(f"{API}/testimonials", headers=auth(free_user["token"]))
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, (list, dict))
        rows = items if isinstance(items, list) else items.get("items", [])
        assert any(t.get("first_name") == "TEST_Img" for t in rows), "image testimonial missing in dashboard list"
        img = next(t for t in rows if t.get("first_name") == "TEST_Img")
        assert img.get("image_url") == "https://example.com/i.png", "image_url not exposed in list API"
        assert all("_id" not in t for t in rows)
