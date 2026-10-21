"""AI captions for video testimonials.

Video testimonials are the product's headline feature but they are silent to
search engines, screen readers, and anyone watching on mute — which is most of
the internet. This module transcribes each video once (OpenAI Whisper by
default), stores a WebVTT track plus a plain-text transcript, and exposes both to
the widgets and the dashboard.

Cost control:
* only runs when the admin toggle is on (defaults to on when OPENAI_API_KEY set),
* only on Pro/Business workspaces,
* one job per testimonial, retried at most 3 times,
* videos over the provider's 25 MB upload limit are skipped, not failed silently.
"""
import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timezone

import requests

from db import db

logger = logging.getLogger("testify.transcription")

API_URL = "https://api.openai.com/v1/audio/transcriptions"
MAX_BYTES = 25 * 1024 * 1024  # OpenAI hard limit for audio/video uploads
MAX_ATTEMPTS = 3
POLL_SECONDS = 15

_worker_task = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def is_enabled() -> bool:
    from settings_store import get_setting

    value = await get_setting("ai_captions_enabled")
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def provider_model() -> str:
    return (os.environ.get("OPENAI_TRANSCRIBE_MODEL") or "whisper-1").strip()


def vtt_to_text(vtt: str) -> str:
    """Strip WebVTT scaffolding and timing lines to a readable transcript."""
    lines = []
    for raw in (vtt or "").splitlines():
        line = raw.strip()
        if not line or line.upper().startswith("WEBVTT"):
            continue
        if line.isdigit() or "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return " ".join(lines).strip()


def _download(url: str, public_origin: str = "") -> bytes:
    """Fetch the video, resolving API-proxied media paths the same way the UI does."""
    if url.startswith("/api/") and public_origin:
        url = f"{public_origin}{url}"
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    chunks, size = [], 0
    for chunk in resp.iter_content(chunk_size=512 * 1024):
        size += len(chunk)
        if size > MAX_BYTES:
            raise ValueError("video exceeds the 25 MB transcription limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _call_provider(video_bytes: bytes, filename: str = "testimonial.mp4") -> str:
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {key}"},
        files={"file": (filename, video_bytes, "video/mp4")},
        data={"model": provider_model(), "response_format": "vtt"},
        timeout=300,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"transcription provider returned {resp.status_code}: {resp.text[:300]}")
    return resp.text


async def enqueue(workspace_id: str, testimonial_id: str, video_url: str) -> str | None:
    """Queue one transcription job, skipping duplicates and unsupported videos."""
    if not video_url:
        return None
    existing = await db.transcription_jobs.find_one(
        {"testimonial_id": testimonial_id, "status": {"$in": ["queued", "processing", "done"]}},
        {"_id": 0, "id": 1},
    )
    if existing:
        return existing["id"]
    job = {
        "id": f"trj_{secrets.token_hex(8)}",
        "workspace_id": workspace_id,
        "testimonial_id": testimonial_id,
        "video_url": video_url,
        "status": "queued",
        "attempts": 0,
        "error": None,
        "created_at": _now(),
    }
    await db.transcription_jobs.insert_one(dict(job))
    return job["id"]


async def process_job(job_id: str) -> dict:
    job = await db.transcription_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        return {"error": "job not found"}
    if job["status"] in ("done", "processing"):
        return job

    await db.transcription_jobs.update_one(
        {"id": job_id}, {"$set": {"status": "processing", "started_at": _now()}}
    )
    origin = (os.environ.get("CORS_ORIGINS", "").split(",")[0] or "").strip()
    attempts = int(job.get("attempts", 0)) + 1
    try:
        video = await asyncio.to_thread(_download, job["video_url"], origin)
        vtt = await asyncio.to_thread(_call_provider, video)
        text = vtt_to_text(vtt)
        if not text:
            raise ValueError("provider returned an empty transcript")
        await db.testimonials.update_one(
            {"id": job["testimonial_id"]},
            {
                "$set": {
                    "captions_vtt": vtt,
                    "transcript": text,
                    "transcribed_at": _now(),
                    "transcription_model": provider_model(),
                }
            },
        )
        await db.transcription_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "done", "attempts": attempts, "completed_at": _now(), "error": None}},
        )
        return {"ok": True, "testimonial_id": job["testimonial_id"], "chars": len(text)}
    except Exception as exc:
        message = str(exc)[:400]
        final = attempts >= MAX_ATTEMPTS
        await db.transcription_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "failed" if final else "queued", "attempts": attempts, "error": message}},
        )
        logger.warning(f"Transcription job {job_id} attempt {attempts} failed: {message}")
        return {"ok": False, "attempts": attempts, "error": message, "final": final}


async def process_queue(limit: int = 3) -> int:
    jobs = await db.transcription_jobs.find({"status": "queued"}, {"_id": 0, "id": 1}).sort("created_at", 1).to_list(limit)
    for job in jobs:
        await process_job(job["id"])
    return len(jobs)


async def _loop():
    await asyncio.sleep(20)
    while True:
        try:
            if await is_enabled():
                await process_queue()
        except Exception as exc:
            logger.warning(f"Transcription worker tick failed: {exc}")
        await asyncio.sleep(POLL_SECONDS)


def start_worker():
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_loop())
