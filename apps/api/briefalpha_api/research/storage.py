"""Encrypted PDF storage on local disk.

PDFs are written to `research_pdfs/{user_id}/{file_id}.pdf.enc`. We use
the same AES-GCM key as the alias_map (`data/.secrets/alias_key`) — the
key is already provisioned by `scripts/init_secrets.sh` and rotating it
together makes operator UX simpler than introducing a second key.

Decryption to a temp file is required by `pdfplumber` which expects a
filesystem path. The temp file is `chmod 0600` and removed after parsing.
"""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from briefalpha_api.settings import RESEARCH_PDFS_DIR, SECRETS_DIR

_NONCE_LEN = 12


def _key() -> bytes:
    path = SECRETS_DIR / "alias_key"
    if not path.exists():
        raise RuntimeError("alias_key missing. Run scripts/init_secrets.sh.")
    raw = path.read_bytes()
    if len(raw) != 32:
        raise RuntimeError(
            f"alias_key length {len(raw)} != 32 bytes (AES-256-GCM)."
        )
    return raw


def encrypted_path_for(user_id: str, file_id: str) -> Path:
    folder = RESEARCH_PDFS_DIR / user_id
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    return folder / f"{file_id}.pdf.enc"


def write_encrypted(user_id: str, file_id: str, plaintext: bytes) -> Path:
    aesgcm = AESGCM(_key())
    nonce = os.urandom(_NONCE_LEN)
    aad = f"{user_id}|{file_id}".encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
    out = encrypted_path_for(user_id, file_id)
    out.write_bytes(nonce + ciphertext)
    out.chmod(0o600)
    return out


def read_encrypted(user_id: str, file_id: str) -> bytes:
    path = encrypted_path_for(user_id, file_id)
    if not path.exists():
        raise FileNotFoundError(f"PDF for {file_id} not present (deleted?)")
    raw = path.read_bytes()
    nonce, ciphertext = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    aad = f"{user_id}|{file_id}".encode("utf-8")
    return AESGCM(_key()).decrypt(nonce, ciphertext, aad)


def delete_encrypted(user_id: str, file_id: str) -> bool:
    path = encrypted_path_for(user_id, file_id)
    if path.exists():
        path.unlink()
        return True
    return False


@contextmanager
def decrypted_temp(user_id: str, file_id: str) -> Iterator[Path]:
    """Yield a temporary path containing the decrypted PDF; cleaned up on exit."""
    plaintext = read_encrypted(user_id, file_id)
    fd, tmp_name = tempfile.mkstemp(suffix=".pdf", prefix=f"{file_id}_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(plaintext)
        os.chmod(tmp_name, 0o600)
        yield Path(tmp_name)
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def list_user_files(user_id: str) -> list[str]:
    """Return file_ids the user has on disk (no DB read)."""
    folder = RESEARCH_PDFS_DIR / user_id
    if not folder.exists():
        return []
    return [p.stem.removesuffix(".pdf") for p in folder.glob("*.pdf.enc")]


def sweep_old_files(*, max_age_days: int) -> int:
    """Delete encrypted files older than `max_age_days`. Returns count deleted."""
    import time

    now = time.time()
    cutoff = now - max_age_days * 86400
    removed = 0
    if not RESEARCH_PDFS_DIR.exists():
        return 0
    for user_dir in RESEARCH_PDFS_DIR.iterdir():
        if not user_dir.is_dir():
            continue
        for path in user_dir.glob("*.pdf.enc"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
    return removed
