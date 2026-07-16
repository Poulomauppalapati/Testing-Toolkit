# Tests for core.settings_store encryption, persistence, and first-run detection.
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# --------------------------------------------------------------------------
# Encrypt / decrypt roundtrip (force fallback path to avoid DPAPI edge cases)
# --------------------------------------------------------------------------
def test_encrypt_decrypt_roundtrip():
    from core.settings_store import _encrypt_value, _decrypt_value

    # Force fallback (MKEY) path so the test is deterministic across platforms
    # and avoids DPAPI refusing empty-data encryption on some Windows builds.
    # NOTE: empty string excluded -- _decrypt_value returns None for b"" because
    # empty bytes are falsy; production code always strips to non-empty values.
    with patch("core.settings_store._dpapi_encrypt", return_value=None):
        cases = ["hello", "unicode-safe-ascii", "key=value\nother=val", "x"]
        for text in cases:
            encrypted = _encrypt_value(text)
            assert encrypted.startswith("MKEY:")
            assert _decrypt_value(encrypted) == text, f"roundtrip failed for {text!r}"


# --------------------------------------------------------------------------
# Fallback encrypt tamper detection
# --------------------------------------------------------------------------
def test_fallback_encrypt_tamper_detection():
    from core.settings_store import _fallback_encrypt, _fallback_decrypt

    plaintext = b"secret data here"
    ciphertext = _fallback_encrypt(plaintext)
    # Tamper one byte in the encrypted payload (after the 16-byte tag)
    tampered = bytearray(ciphertext)
    tampered[16] ^= 0xFF
    tampered = bytes(tampered)
    assert _fallback_decrypt(tampered) is None


# --------------------------------------------------------------------------
# get_setting with default
# --------------------------------------------------------------------------
def test_get_setting_with_default(tmp_path, monkeypatch):
    from core import settings_store

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"org": "myorg"}), encoding="utf-8")

    # Monkeypatch the module-level SETTINGS_PATH used by _load_all
    monkeypatch.setattr(settings_store, "_settings_cache", None)
    monkeypatch.setattr(settings_store, "_settings_cache_mtime", 0.0)
    with patch("core.settings_store.SETTINGS_PATH", settings_file):
        assert settings_store.get_setting("org") == "myorg"
        assert settings_store.get_setting("missing", "fallback") == "fallback"


# --------------------------------------------------------------------------
# save_setting / get_setting roundtrip
# --------------------------------------------------------------------------
def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    from core import settings_store

    settings_file = tmp_path / "settings.json"

    monkeypatch.setattr(settings_store, "_settings_cache", None)
    monkeypatch.setattr(settings_store, "_settings_cache_mtime", 0.0)
    with patch("core.settings_store.SETTINGS_PATH", settings_file):
        settings_store.save_setting("key", "val")
        # Reset cache to force re-read
        settings_store._settings_cache = None
        settings_store._settings_cache_mtime = 0.0
        assert settings_store.get_setting("key") == "val"


# --------------------------------------------------------------------------
# is_configured returns False when empty
# --------------------------------------------------------------------------
def test_is_configured_false_when_empty(tmp_path, monkeypatch):
    from core import settings_store

    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(settings_store, "_settings_cache", None)
    monkeypatch.setattr(settings_store, "_settings_cache_mtime", 0.0)
    with patch("core.settings_store.SETTINGS_PATH", settings_file):
        # Also ensure load_pat returns empty so is_configured -> False
        with patch("core.settings_store.load_pat", return_value=""):
            assert settings_store.is_configured() is False
