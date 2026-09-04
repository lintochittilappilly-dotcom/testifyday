"""Iteration 11 — /api/upload size-gate ordering (per-plan video cap vs global MAX_SIZE).

Why in-process instead of HTTP?
  1. This environment has no S3_BUCKET_NAME, so a real allowed upload always ends in
     500 at the storage layer — the 200 success path cannot be asserted over HTTP.
     `server.put_object` is therefore monkeypatched to a no-op (as requested).
  2. python-multipart's parser is CPU-bound and takes minutes to parse a 100MB+
     multipart body (verified with faulthandler), which made HTTP-level 100MB/210MB
     uploads effectively hang. Calling the endpoint coroutine directly exercises the
     exact same size-gate + storage + db-persistence code without the parser cost.

HTTP-level coverage of the same gate (with small payloads + an admin cap override)
lives in tests/test_video_limits.py::TestUploadSizeCaps.

All coroutines share ONE event loop because db.py's motor client is a module-level
singleton bound to the first loop that uses it.
"""
import asyncio
import io
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

sys.path.insert(0, "/app/backend")

MB = 1024 * 1024


@pytest.fixture(scope="module")
def loop():
    lp = asyncio.new_event_loop()
    asyncio.set_event_loop(lp)
    yield lp
    lp.close()


@pytest.fixture(scope="module")
def srv(loop):
    """Import the app and rebind motor to OUR loop.

    tests/test_stripe_diagnostics.py imports `server` and drives it through
    fastapi TestClient, which leaves db.py's motor client bound to a loop that is
    already closed by the time this module runs. Rebinding a fresh client (and
    restoring it afterwards) keeps both suites working in any order.
    """
    import os

    from motor.motor_asyncio import AsyncIOMotorClient

    asyncio.set_event_loop(loop)
    import db as db_mod
    import settings_store
    import server

    fresh_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    fresh_db = fresh_client[os.environ["DB_NAME"]]
    originals = (db_mod.db, server.db, settings_store.db)
    db_mod.db = fresh_db
    server.db = fresh_db
    settings_store.db = fresh_db

    calls = []

    def _fake_put_object(path, data, content_type):
        calls.append({"path": path, "size": len(data), "content_type": content_type})
        return {"path": path}

    server.put_object = _fake_put_object
    yield server, calls

    async def _cleanup():
        for c in calls:
            await server.db.files.delete_many({"storage_path": c["path"]})

    loop.run_until_complete(_cleanup())
    fresh_client.close()
    db_mod.db, server.db, settings_store.db = originals


@pytest.fixture(autouse=True)
def clear_upload_rate_limit(srv):
    """/api/upload is rate limited to 30 calls / 60s per client host."""
    server = srv[0]
    for k in [k for k in list(server._rate_store) if k.startswith("upload:")]:
        server._rate_store.pop(k, None)


def _fake_request():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


def _upload(loop, server, name, size_bytes, ct):
    """Returns (status_code, detail_or_body). status 200 => body dict."""
    up = UploadFile(
        file=io.BytesIO(b"0" * size_bytes),
        filename=name,
        size=size_bytes,
        headers=Headers({"content-type": ct}),
    )
    try:
        body = loop.run_until_complete(server.upload(_fake_request(), up))
        return 200, body
    except HTTPException as e:
        return e.status_code, e.detail


# ---------- video: the global MAX_SIZE (80MB) must NOT apply ----------

class TestVideoSizeGate:
    def test_100mb_business_video_succeeds(self, loop, srv):
        server, calls = srv
        status, body = _upload(loop, server, "TEST_100mb.mp4", 100 * MB, "video/mp4")
        assert status == 200, f"expected success, got {status}: {body}"
        assert body["path"].startswith("testify/uploads/"), body
        assert body["url"] == f"/api/media/{body['path']}", body
        assert calls[-1]["size"] == 100 * MB
        assert calls[-1]["content_type"] == "video/mp4"

    def test_81mb_video_succeeds_global_max_not_applied(self, loop, srv):
        server, _ = srv
        status, body = _upload(loop, server, "TEST_81mb.webm", 81 * MB, "video/webm")
        assert status == 200, f"81MB video must not hit the 80MB global cap: {status} {body}"

    def test_210mb_video_rejected_with_business_cap_message(self, loop, srv):
        server, _ = srv
        status, detail = _upload(loop, server, "TEST_210mb.mp4", 210 * MB, "video/mp4")
        assert status == 413, f"expected 413, got {status}: {detail}"
        assert detail == "Video is too large. Max 200MB.", detail

    def test_video_persisted_in_files_collection(self, loop, srv):
        server, _ = srv
        status, body = _upload(loop, server, "TEST_persist.mp4", 2 * MB, "video/mp4")
        assert status == 200, body
        doc = loop.run_until_complete(
            server.db.files.find_one({"storage_path": body["path"]}, {"_id": 0})
        )
        assert doc is not None, "file doc not persisted"
        assert doc["content_type"] == "video/mp4"
        assert doc["size"] == 2 * MB
        assert doc["is_deleted"] is False


# ---------- image: hard 5MB cap ----------

class TestImageSizeGate:
    def test_6mb_image_rejected(self, loop, srv):
        server, _ = srv
        status, detail = _upload(loop, server, "TEST_6mb.png", 6 * MB, "image/png")
        assert status == 413, f"expected 413, got {status}: {detail}"
        assert detail == "Image is too large. Max 5MB.", detail

    def test_5mb_image_succeeds(self, loop, srv):
        server, calls = srv
        status, body = _upload(loop, server, "TEST_5mb.jpg", 5 * MB, "image/jpeg")
        assert status == 200, f"5MB image should pass: {status} {body}"
        assert calls[-1]["size"] == 5 * MB

    def test_unsupported_type_rejected_before_size_check(self, loop, srv):
        server, _ = srv
        status, detail = _upload(loop, server, "TEST_x.exe", 1024, "application/x-msdownload")
        assert status == 400, detail
        assert "unsupported" in str(detail).lower(), detail


# ---------- admin override changes the video cap ----------

class TestAdminOverrideVideoCap:
    @pytest.fixture
    def business_500mb(self, loop, srv):
        """Set video_limits.business.max_size_mb=500 through the admin API surface."""
        server, _ = srv
        loop.run_until_complete(
            server.update_settings({"video_limits": {"business": {"max_size_mb": 500}}})
        )
        limits = loop.run_until_complete(server.get_video_limits())
        assert limits["business"]["max_size_mb"] == 500, limits
        assert limits["pro"]["max_size_mb"] == 50, "pro must keep its default"
        yield
        loop.run_until_complete(server.update_settings({"video_limits": {}}))
        assert loop.run_until_complete(server.get_video_limits())["business"]["max_size_mb"] == 200

    def test_300mb_video_allowed_after_override(self, loop, srv, business_500mb):
        server, _ = srv
        status, body = _upload(loop, server, "TEST_300mb.mp4", 300 * MB, "video/mp4")
        assert status == 200, f"300MB should pass with a 500MB cap: {status} {body}"

    def test_600mb_video_rejected_after_override(self, loop, srv, business_500mb):
        server, _ = srv
        status, detail = _upload(loop, server, "TEST_600mb.mp4", 600 * MB, "video/mp4")
        assert status == 413, f"expected 413, got {status}: {detail}"
        assert detail == "Video is too large. Max 500MB.", detail

    def test_cap_restored_to_200_after_reset(self, loop, srv):
        server, _ = srv
        status, detail = _upload(loop, server, "TEST_210mb_again.mp4", 210 * MB, "video/mp4")
        assert status == 413, detail
        assert detail == "Video is too large. Max 200MB.", detail
