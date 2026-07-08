"""
seal_env.py -- encrypt the LLM service-account credentials into .env.enc.

WHAT THIS IS FOR
    The web agent installs its files from GitHub via the update manifest, so
    the LLM credentials have to live somewhere in git to reach end users. We
    never commit the plaintext key: instead we commit only the Fernet-sealed
    .env.enc (ciphertext), and the agent opens it at runtime
    (core.app_config._portable_decrypt_bytes).

    Run this manually whenever you SET or ROTATE the key. Only YOU run it; the
    plaintext source never gets committed.

INPUT (first match wins)
    1. A plaintext .env at agent-bundle/src/.env  (KEY=VALUE lines; gitignored)
    2. Otherwise the current process environment. Accepts either the proxy-style
       names (LLM_UPSTREAM_API_KEY / LLM_UPSTREAM_BASE_URL) or the plain names
       (API_KEY / BASE_URL), plus optional MODEL_* / EMBED_MODEL overrides.

OUTPUT
    agent-bundle/src/.env.enc  (commit THIS; it is ciphertext)

USAGE
    python agent-bundle/tools/seal_env.py
    # or from a specific plaintext file:
    python agent-bundle/tools/seal_env.py path/to/plaintext.env

ponytail: obfuscation ceiling -- the decrypt passphrase ships inside the agent
(core.app_config), so this protects against casual inspection, not a determined
operator on the machine. Rotate the service key or use the server-side proxy
(app/api/llm) for true secrecy.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sys
from pathlib import Path

# INPUT/OUTPUT anchored to the repo layout (this file lives in
# agent-bundle/tools/, src is a sibling).
_SRC_DIR: Path = Path(__file__).resolve().parent.parent / "src"
INPUT_PATH: Path = _SRC_DIR / ".env"
OUTPUT_PATH: Path = _SRC_DIR / ".env.enc"

# Config keys we seal when building from the environment. Model tiers default to
# the values the toolkit ships with; override any of them via env if needed.
_MODEL_DEFAULTS: dict[str, str] = {
    "MODEL_SMALL": "azure.gpt-4o-mini",
    "MODEL_MEDIUM": "bedrock.anthropic.claude-sonnet-4-6",
    "MODEL_LARGE": "bedrock.anthropic.claude-opus-4-6",
    "MODEL_GENERATE": "bedrock.anthropic.claude-opus-4-6",
    "MODEL_CHAT": "bedrock.anthropic.claude-sonnet-4-6",
    "MODEL_EXTRACT": "azure.gpt-4o",
    "MODEL_OCR": "azure.gpt-4o",
    "MODEL_RERANK": "azure.gpt-4o-mini",
    "MODEL_CONTEXTUALIZE": "azure.gpt-4o-mini",
    "EMBED_MODEL": "azure.text-embedding-3-small",
}


def _portable_fernet_key() -> bytes:
    """MUST match core.app_config._portable_fernet_key exactly."""
    secret = b"TestingToolkit/GenAI/bundled-env/v1"
    return base64.urlsafe_b64encode(hashlib.sha256(secret).digest())


def _env_text_from_process() -> str:
    """Build the plaintext .env body from process environment variables.

    Reads the secret from LLM_UPSTREAM_API_KEY or API_KEY, and the endpoint
    from LLM_UPSTREAM_BASE_URL or BASE_URL. Raises if the key is missing so we
    never seal an empty credential.
    """
    api_key = os.environ.get("LLM_UPSTREAM_API_KEY") or os.environ.get("API_KEY")
    base_url = (
        os.environ.get("LLM_UPSTREAM_BASE_URL")
        or os.environ.get("BASE_URL")
    )
    if not api_key:
        raise SystemExit(
            "[ERROR] No API key found. Set LLM_UPSTREAM_API_KEY (or API_KEY), "
            "or create a plaintext .env at " + str(INPUT_PATH)
        )
    if not base_url:
        raise SystemExit(
            "[ERROR] No base URL found. Set LLM_UPSTREAM_BASE_URL (or BASE_URL)."
        )

    lines: list[str] = [
        "# Sealed by seal_env.py -- do not commit the plaintext form.",
        f"API_KEY={api_key.strip()}",
        f"BASE_URL={base_url.strip()}",
    ]
    for name, default in _MODEL_DEFAULTS.items():
        lines.append(f"{name}={os.environ.get(name, default).strip()}")
    provider = os.environ.get("LLM_PROVIDER_FORMAT")
    if provider:
        lines.append(f"LLM_PROVIDER_FORMAT={provider.strip()}")
    return "\n".join(lines) + "\n"


def _read_plaintext(explicit: str | None) -> str:
    """Resolve the plaintext env body: explicit path > INPUT_PATH > process env."""
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise SystemExit(f"[ERROR] Plaintext file not found: {path}")
        print(f"[INFO] Sealing from explicit file: {path}")
        return path.read_text(encoding="utf-8")
    if INPUT_PATH.is_file():
        print(f"[INFO] Sealing from plaintext .env: {INPUT_PATH}")
        return INPUT_PATH.read_text(encoding="utf-8")
    print("[INFO] No plaintext .env found; sealing from process environment.")
    return _env_text_from_process()


def main(argv: list[str]) -> int:
    from cryptography.fernet import Fernet

    explicit = argv[1] if len(argv) > 1 else None
    plaintext = _read_plaintext(explicit)

    # Validate the body parses and carries the required secret before sealing.
    keys = {
        ln.split("=", 1)[0].strip()
        for ln in plaintext.splitlines()
        if "=" in ln and not ln.strip().startswith("#")
    }
    missing = {"API_KEY", "BASE_URL"} - keys
    if missing:
        raise SystemExit(
            f"[ERROR] Plaintext is missing required keys: {sorted(missing)}"
        )

    token = Fernet(_portable_fernet_key()).encrypt(plaintext.encode("utf-8"))
    OUTPUT_PATH.write_bytes(token)

    # Verify the sealed blob opens again (fail loud rather than ship a dud).
    reopened = Fernet(_portable_fernet_key()).decrypt(OUTPUT_PATH.read_bytes())
    if reopened != plaintext.encode("utf-8"):
        raise SystemExit("[ERROR] Verification failed: sealed blob did not open")

    print(f"[SUCCESS] Wrote {OUTPUT_PATH} ({len(token)} bytes ciphertext)")
    print("[INFO] Commit ONLY the .env.enc; keep the plaintext out of git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
