"""S3-compatible object storage for user uploads (avatars, testimonial images/videos)."""
import os
import re
import boto3
from botocore.client import Config

APP_NAME = "testify"

_REGION_RE = re.compile(r"\b[a-z]{2}-[a-z]+(?:-[a-z]+)?-\d+\b")


def _clean_region(raw: str) -> str:
    """Accept either 'us-east-1' or 'US East (N. Virginia) us-east-1' — extract the code.
    Falls back to 'us-east-1' when no valid AWS region code is present."""
    if not raw:
        return "us-east-1"
    raw = raw.strip()
    m = _REGION_RE.search(raw.lower())
    return m.group(0) if m else "us-east-1"


_BUCKET = (os.environ.get("S3_BUCKET_NAME") or "").strip()
_REGION = _clean_region(os.environ.get("AWS_REGION", "us-east-1"))
_PUBLIC_BASE = (os.environ.get("S3_PUBLIC_URL") or "").rstrip("/")
_ENDPOINT = (os.environ.get("S3_ENDPOINT_URL") or "").strip() or None  # R2 / MinIO override

_client = None


def _s3():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            region_name=_REGION,
            endpoint_url=_ENDPOINT,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )
    return _client


def init_storage(force: bool = False):
    """Verify bucket is reachable at startup. Raises on misconfiguration."""
    if not _BUCKET:
        raise RuntimeError("S3_BUCKET_NAME is not configured")
    _s3().head_bucket(Bucket=_BUCKET)
    return True


def put_object(path: str, data: bytes, content_type: str) -> dict:
    _s3().put_object(
        Bucket=_BUCKET,
        Key=path,
        Body=data,
        ContentType=content_type,
        CacheControl="public, max-age=31536000",
    )
    return {"path": path}


def get_object(path: str):
    obj = _s3().get_object(Bucket=_BUCKET, Key=path)
    return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")


def public_url(path: str) -> str:
    """Direct public URL if bucket/CDN is public, else API-proxied URL."""
    if _PUBLIC_BASE:
        return f"{_PUBLIC_BASE}/{path}"
    return f"/api/media/{path}"
