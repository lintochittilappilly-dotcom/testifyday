"""Unit tests for backend/storage.py region normalization (_clean_region) and init_storage guard."""
import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage as storage_mod  # noqa: E402


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("us-east-1", "us-east-1"),
        ("US East (N. Virginia) us-east-1", "us-east-1"),
        ("eu-west-2", "eu-west-2"),
        ("EU (London) eu-west-2", "eu-west-2"),
        (" ap-south-1 ", "ap-south-1"),
        ("", "us-east-1"),
        (None, "us-east-1"),
    ],
)
def test_clean_region(raw, expected):
    assert storage_mod._clean_region(raw) == expected


def test_module_region_from_display_label(monkeypatch):
    """Fresh import with AWS_REGION as display label must resolve _REGION to the code."""
    monkeypatch.setenv("AWS_REGION", "US East (N. Virginia) us-east-1")
    mod = importlib.reload(storage_mod)
    try:
        assert mod._REGION == "us-east-1"
    finally:
        monkeypatch.delenv("AWS_REGION", raising=False)
        importlib.reload(storage_mod)


def test_init_storage_raises_without_bucket(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    mod = importlib.reload(storage_mod)
    try:
        assert mod._BUCKET == ""
        with pytest.raises(RuntimeError) as exc:
            mod.init_storage()
        assert "S3_BUCKET_NAME" in str(exc.value)
    finally:
        importlib.reload(storage_mod)


def test_public_url_falls_back_to_api_proxy(monkeypatch):
    monkeypatch.delenv("S3_PUBLIC_URL", raising=False)
    mod = importlib.reload(storage_mod)
    try:
        assert mod.public_url("avatars/x.png") == "/api/media/avatars/x.png"
    finally:
        importlib.reload(storage_mod)


def test_env_bucket_state_unchanged_after_reloads():
    """Sanity: reloading storage must not leak modified env into the live module."""
    assert storage_mod._BUCKET == (os.environ.get("S3_BUCKET_NAME") or "").strip()
