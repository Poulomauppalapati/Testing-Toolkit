"""
pat_store.py
Cross-platform secure storage for the ADO Personal Access Token.

Strategy:
  1. Try OS keyring (Windows Credential Manager / macOS Keychain /
     Linux Secret Service).
  2. On failure, fall back to a DPAPI-encrypted file (Windows) or
     PBKDF2-derived-key encrypted file (other platforms).
"""

from __future__ import annotations

import base64
import hashlib
import os
import stat
import sys
from pathlib import Path
from typing import Final

# Hardcoded paths
HOME_DIR: Final[Path] = Path.home()
FALLBACK_PATH: Final[Path] = HOME_DIR / ".ado_pdf_packager_token"
SERVICE_NAME: Final[str] = "ado_pdf_packager"
USERNAME: Final[str] = "default"


def _try_keyring_get() -> str | None:
    try:
        import keyring  # type: ignore
        val = keyring.get_password(SERVICE_NAME, USERNAME)
        return val if val else None
    except Exception:
        return None


def _try_keyring_set(token: str) -> bool:
    try:
        import keyring  # type: ignore
        keyring.set_password(SERVICE_NAME, USERNAME, token)
        return True
    except Exception:
        return False


def _try_keyring_delete() -> bool:
    try:
        import keyring  # type: ignore
        keyring.delete_password(SERVICE_NAME, USERNAME)
        return True
    except Exception:
        return False


def _dpapi_encrypt(data: bytes) -> bytes | None:
    """Encrypt with Windows DPAPI (CurrentUser scope)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes

        class _Blob(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_char))]

        p_in = _Blob(len(data), ctypes.create_string_buffer(data, len(data)))
        p_out = _Blob()
        if ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(p_in), None, None, None, None, 0,
            ctypes.byref(p_out)
        ):
            enc = ctypes.string_at(p_out.pbData, p_out.cbData)
            ctypes.windll.kernel32.LocalFree(p_out.pbData)
            return enc
    except Exception:
        pass
    return None


def _dpapi_decrypt(data: bytes) -> bytes | None:
    """Decrypt with Windows DPAPI (CurrentUser scope)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes

        class _Blob(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_char))]

        p_in = _Blob(len(data), ctypes.create_string_buffer(data, len(data)))
        p_out = _Blob()
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(p_in), None, None, None, None, 0,
            ctypes.byref(p_out)
        ):
            dec = ctypes.string_at(p_out.pbData, p_out.cbData)
            ctypes.windll.kernel32.LocalFree(p_out.pbData)
            return dec
    except Exception:
        pass
    return None


def _derive_key() -> bytes:
    """Non-Windows fallback: derive a machine+user-specific key via PBKDF2."""
    try:
        user = os.getlogin()
    except OSError:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or "x"
    import platform
    salt = f"ttk-pat-{platform.node()}-{user}".encode()
    return hashlib.pbkdf2_hmac("sha256", salt, b"ttk-pat-store", 100_000)


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR data with key (repeating key if shorter)."""
    kl = len(key)
    return bytes(b ^ key[i % kl] for i, b in enumerate(data))


def _file_get() -> str | None:
    if not FALLBACK_PATH.exists():
        return None
    try:
        raw = FALLBACK_PATH.read_bytes()
        if not raw:
            return None
        # Try DPAPI first (Windows)
        dec = _dpapi_decrypt(raw)
        if dec:
            return dec.decode("utf-8")
        # Fallback: XOR with derived key
        dec = _xor_bytes(raw, _derive_key())
        return dec.decode("utf-8")
    except Exception:
        # Legacy base64 migration path
        try:
            text = FALLBACK_PATH.read_text(encoding="ascii").strip()
            return base64.b64decode(text.encode("ascii")).decode("utf-8")
        except Exception:
            return None


def _file_set(token: str) -> bool:
    try:
        data = token.encode("utf-8")
        # Try DPAPI (Windows)
        enc = _dpapi_encrypt(data)
        if enc:
            FALLBACK_PATH.write_bytes(enc)
        else:
            # Non-Windows: XOR with derived key
            FALLBACK_PATH.write_bytes(_xor_bytes(data, _derive_key()))
        try:
            os.chmod(FALLBACK_PATH, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
        return True
    except Exception:
        return False


def _file_delete() -> bool:
    try:
        if FALLBACK_PATH.exists():
            FALLBACK_PATH.unlink()
        return True
    except Exception:
        return False


def load_pat() -> str | None:
    """Return stored PAT or None if absent."""
    val = _try_keyring_get()
    if val:
        return val
    return _file_get()


def save_pat(token: str) -> bool:
    """Persist PAT. Returns True if any backend succeeded."""
    if not token or not token.strip():
        return False
    token = token.strip()
    if _try_keyring_set(token):
        return True
    return _file_set(token)


def clear_pat() -> bool:
    """Remove the stored PAT from all backends."""
    a = _try_keyring_delete()
    b = _file_delete()
    return a or b
