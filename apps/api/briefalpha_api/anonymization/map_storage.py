"""AES-GCM read/write for `data/alias_maps/{brief_id}.enc`."""
from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from briefalpha_api.anonymization.alias import AliasContext
from briefalpha_api.settings import ALIAS_MAPS_DIR, SECRETS_DIR

_NONCE_LEN = 12


def _key() -> bytes:
    path: Path = SECRETS_DIR / "alias_key"
    if not path.exists():
        raise RuntimeError(
            "alias_key missing. Run `bash scripts/init_secrets.sh` first."
        )
    raw = path.read_bytes()
    if len(raw) != 32:
        raise RuntimeError(
            f"alias_key length {len(raw)} != 32 bytes (AES-256-GCM key)."
        )
    return raw


def _path_for(brief_id: str) -> Path:
    ALIAS_MAPS_DIR.mkdir(parents=True, exist_ok=True)
    return ALIAS_MAPS_DIR / f"{brief_id}.enc"


def encrypt_alias_map(brief_id: str, ctx: AliasContext) -> Path:
    plaintext = json.dumps(ctx.to_dict(), ensure_ascii=False).encode("utf-8")
    aesgcm = AESGCM(_key())
    import os

    nonce = os.urandom(_NONCE_LEN)
    ciphertext = aesgcm.encrypt(nonce, plaintext, brief_id.encode("utf-8"))
    out = _path_for(brief_id)
    out.write_bytes(nonce + ciphertext)
    out.chmod(0o600)
    return out


def decrypt_alias_map(brief_id: str) -> AliasContext:
    path = _path_for(brief_id)
    if not path.exists():
        raise FileNotFoundError(f"alias_map for {brief_id} not present (expired?)")
    raw = path.read_bytes()
    nonce, ciphertext = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    aesgcm = AESGCM(_key())
    plaintext = aesgcm.decrypt(nonce, ciphertext, brief_id.encode("utf-8"))
    return AliasContext.from_dict(json.loads(plaintext.decode("utf-8")))


def delete_alias_map(brief_id: str) -> bool:
    path = _path_for(brief_id)
    if path.exists():
        path.unlink()
        return True
    return False
