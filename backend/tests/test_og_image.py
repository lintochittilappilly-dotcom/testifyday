"""Public wall social card: /api/og/wall/{slug}.png plus the og_image field.

Crawlers (Twitter/X, LinkedIn, Slack) only read PNG/JPEG, so the endpoint has to
return a real 1200x630 PNG, not an SVG, and cache it.
"""
import struct

from conftest import API


def _png_size(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "response is not a PNG"
    return struct.unpack(">II", data[16:24])


class TestWallOgImage:
    def test_unknown_wall_is_404(self, api):
        r = api.get(f"{API}/og/wall/no-such-wall-xyz.png")
        assert r.status_code == 404, r.text[:200]

    def test_wall_payload_exposes_og_image(self, api, free_user, approved_wall):
        r = api.get(f"{API}/public/wall/{approved_wall['slug']}")
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["count"] == 3
        assert body["og_image"] == f"/api/og/wall/{approved_wall['slug']}.png", body.get("og_image")

    def test_returns_1200x630_png(self, api, approved_wall):
        r = api.get(f"{API}/og/wall/{approved_wall['slug']}.png")
        assert r.status_code == 200, r.text[:200]
        assert r.headers["content-type"] == "image/png"
        assert "max-age" in r.headers.get("cache-control", "")
        assert _png_size(r.content) == (1200, 630)
        assert len(r.content) > 5000, "image looks empty"

    def test_count_in_image_matches_wall(self, api, approved_wall, mongo):
        """A 4th approved testimonial must change the rendered card."""
        before = api.get(f"{API}/og/wall/{approved_wall['slug']}.png").content
        mongo.testimonials.insert_one({
            "id": "tst_og_extra", "workspace_id": approved_wall["ws_id"], "collection_id": "c",
            "first_name": "TEST_Og", "last_name": "", "text": "one more", "rating": 5,
            "status": "approved", "featured": False, "tags": [],
            "approved_at": "2026-02-01T00:00:00+00:00", "created_at": "2026-02-01T00:00:00+00:00",
        })
        after = api.get(f"{API}/og/wall/{approved_wall['slug']}.png").content
        assert before != after, "card did not change after a testimonial was approved"
