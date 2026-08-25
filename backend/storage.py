"""S3-compatible object storage for user uploads (avatars, testimonial images/videos)."""
import os
import boto3
from botocore.client import Config

APP_NAME = "testify"

_BUCKET = os.environ.get("S3_BUCKET_NAME")
_REGION = os.environ.get("AWS_REGION", "us-east-1")
_PUBLIC_BASE = (os.environ.get("S3_PUBLIC_URL") or "").rstrip("/")
_ENDPOINT = os.environ.get("S3_ENDPOINT_URL") or None  # Cloudflare R2 / MinIO override

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
