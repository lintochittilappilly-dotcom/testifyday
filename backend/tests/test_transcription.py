"""AI captions for video testimonials.

The provider call is stubbed here (no OpenAI key in CI/local), but everything
else is exercised for real: the job queue, the transcript/VTT write-back, and the
public caption endpoint the video widget points at.
"""
import asyncio
import uuid

import pytest

import transcription
from conftest import API, auth

SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:03.500
<v Speaker>We switched to Testify in an afternoon.

00:00:03.500 --> 00:00:07.000
We switched to Testify in an afternoon.
The video wall did the rest.
"""


@pytest.fixture(scope="module")
def loop():
    """Run the transcription coroutines on one loop with their own motor client.

    Motor caches the loop it first runs on; other test modules import the app on
    a different loop, so this module gets a dedicated client (same database).
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    from conftest import DB_NAME, MONGO_URL

    lp = asyncio.new_event_loop()
    asyncio.set_event_loop(lp)
    original = transcription.db
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    transcription.db = client[DB_NAME]
    yield lp
    client.close()
    transcription.db = original
    lp.close()


@pytest.fixture(scope="module")
def pro(api, mongo):
    """A Pro workspace with one published collection (captions are paid-only)."""
    email = f"test_cap_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={"name": "TEST_ Captions", "email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text[:300]
    token = r.json()["token"]
    ws = api.get(f"{API}/workspace", headers=auth(token)).json()
    mongo.workspaces.update_one({"id": ws["id"]}, {"$set": {"plan": "pro"}})
    page = api.post(f"{API}/collections", headers=auth(token), json={"name": "TEST_ Captions Page", "require_email": False})
    assert page.status_code == 200, page.text[:300]
    col = api.put(
        f"{API}/collections/{page.json()['id']}",
        headers=auth(token),
        json={"published": True, "allow_video": True},
    ).json()
    return {"token": token, "ws": ws, "col": col}


@pytest.fixture
def stub_provider(monkeypatch):
    """Replace the network calls so the job logic is tested without an API key."""
    calls = {"download": 0, "provider": 0, "vtt": SAMPLE_VTT}

    def fake_download(url, public_origin=""):
        calls["download"] += 1
        assert url, "job must carry a video url"
        return b"fake-video-bytes"

    def fake_provider(video, filename="testimonial.mp4"):
        calls["provider"] += 1
        assert video == b"fake-video-bytes"
        return calls["vtt"]

    monkeypatch.setattr(transcription, "_download", fake_download)
    monkeypatch.setattr(transcription, "_call_provider", fake_provider)
    return calls


def _video_testimonial(mongo, ws_id, col_id, status="approved", captions=None):
    tid = f"tst_tr_{uuid.uuid4().hex[:6]}"
    doc = {
        "id": tid,
        "workspace_id": ws_id,
        "collection_id": col_id,
        "first_name": "TEST_Caption",
        "last_name": "",
        "email": "",
        "company": "",
        "role": "",
        "text": "",
        "video_url": "https://example.com/testimonial.mp4",
        "status": status,
        "featured": False,
        "tags": [],
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    if captions:
        doc["captions_vtt"] = captions
        doc["transcript"] = "We switched to Testify in an afternoon."
    mongo.testimonials.insert_one(doc)
    return tid


class TestVttParsing:
    def test_strips_timings_and_dedupes_rolling_lines(self):
        text = transcription.vtt_to_text(SAMPLE_VTT)
        assert "WEBVTT" not in text
        assert "-->" not in text
        assert "00:00" not in text
        assert text.count("We switched to Testify in an afternoon.") == 1, text
        assert "The video wall did the rest." in text

    def test_empty_input(self):
        assert transcription.vtt_to_text("") == ""


class TestJobQueue:
    def test_job_writes_transcript_and_vtt(self, loop, mongo, pro, stub_provider):
        tid = _video_testimonial(mongo, pro["ws"]["id"], pro["col"]["id"])
        job_id = loop.run_until_complete(transcription.enqueue(pro["ws"]["id"], tid, "https://example.com/testimonial.mp4"))
        assert job_id and job_id.startswith("trj_")

        result = loop.run_until_complete(transcription.process_job(job_id))
        assert result.get("ok") is True, result
        assert stub_provider["provider"] == 1

        doc = mongo.testimonials.find_one({"id": tid})
        assert "We switched to Testify" in doc["transcript"]
        assert doc["captions_vtt"].startswith("WEBVTT")

        job = mongo.transcription_jobs.find_one({"id": job_id})
        assert job["status"] == "done"

    def test_enqueue_is_idempotent(self, loop, mongo, pro):
        tid = _video_testimonial(mongo, pro["ws"]["id"], pro["col"]["id"])
        first = loop.run_until_complete(transcription.enqueue(pro["ws"]["id"], tid, "https://example.com/v.mp4"))
        second = loop.run_until_complete(transcription.enqueue(pro["ws"]["id"], tid, "https://example.com/v.mp4"))
        assert first == second, "one video should only ever have one active job"

    def test_provider_failure_retries_then_fails(self, loop, mongo, pro, monkeypatch):
        tid = _video_testimonial(mongo, pro["ws"]["id"], pro["col"]["id"])
        job_id = loop.run_until_complete(transcription.enqueue(pro["ws"]["id"], tid, "https://example.com/v.mp4"))

        monkeypatch.setattr(transcription, "_download", lambda url, public_origin="": b"x")

        def boom(video, filename="testimonial.mp4"):
            raise RuntimeError("429 rate limited")

        monkeypatch.setattr(transcription, "_call_provider", boom)
        results = [loop.run_until_complete(transcription.process_job(job_id)) for _ in range(transcription.MAX_ATTEMPTS)]
        assert [r.get("ok") for r in results] == [False] * transcription.MAX_ATTEMPTS
        assert results[-1]["final"] is True
        job = mongo.transcription_jobs.find_one({"id": job_id})
        assert job["status"] == "failed"
        assert "429" in job["error"]
        assert mongo.testimonials.find_one({"id": tid}).get("transcript") is None


class TestCaptionEndpoints:
    def test_captions_served_only_for_approved(self, api, mongo, pro):
        pending = _video_testimonial(mongo, pro["ws"]["id"], pro["col"]["id"], status="pending", captions=SAMPLE_VTT)
        approved = _video_testimonial(mongo, pro["ws"]["id"], pro["col"]["id"], status="approved", captions=SAMPLE_VTT)

        r = api.get(f"{API}/public/testimonial/{pending}/captions.vtt")
        assert r.status_code == 404, "unapproved captions must not be public"

        r = api.get(f"{API}/public/testimonial/{approved}/captions.vtt")
        assert r.status_code == 200, r.text[:200]
        assert r.headers["content-type"].startswith("text/vtt")
        assert r.text.startswith("WEBVTT")

    def test_public_wall_exposes_captions_url(self, api, mongo, pro):
        _video_testimonial(mongo, pro["ws"]["id"], pro["col"]["id"], status="approved", captions=SAMPLE_VTT)
        wall = api.get(f"{API}/public/wall/{api.get(f'{API}/workspace', headers=auth(pro['token'])).json()['slug']}").json()
        captioned = [t for t in wall["testimonials"] if t.get("captions_url")]
        assert captioned, "approved captioned video missing captions_url"
        assert captioned[0]["captions_url"].endswith(".vtt")
        assert captioned[0]["transcript"]

    def test_transcribe_endpoint_requires_video(self, api, mongo, pro):
        tid = f"tst_text_{uuid.uuid4().hex[:6]}"
        mongo.testimonials.insert_one({
            "id": tid, "workspace_id": pro["ws"]["id"], "collection_id": pro["col"]["id"],
            "first_name": "TEST_Text", "last_name": "", "text": "written only", "status": "approved",
            "featured": False, "tags": [], "created_at": "2026-01-01T00:00:00+00:00",
        })
        r = api.post(f"{API}/testimonials/{tid}/transcribe", headers=auth(pro["token"]))
        assert r.status_code == 400, r.text[:200]
        assert "video" in r.json()["detail"].lower()
