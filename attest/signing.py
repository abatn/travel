"""Ed25519-Signaturen für Attestierungen.

Kanonisches JSON (sortierte Schlüssel, keine Leerzeichen) wird signiert.
Die Signatur steht base64url-kodiert im Feld `signature.value`.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def canonical_bytes(document: dict[str, Any]) -> bytes:
    """Stabile Bytes für die Signatur (ohne Signaturfeld)."""
    payload = {k: v for k, v in document.items() if k != "signature"}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True)
class IssuerKey:
    private_key: Ed25519PrivateKey
    key_id: str
    public_key_b64: str

    def sign(self, document: dict[str, Any]) -> dict[str, Any]:
        signature = self.private_key.sign(canonical_bytes(document))
        signed = dict(document)
        signed["signature"] = {
            "alg": "Ed25519",
            "key_id": self.key_id,
            "value": b64u(signature),
        }
        return signed


def load_or_create_key(path: Path) -> IssuerKey:
    """Lädt den Aussteller-Schlüssel oder erzeugt ihn beim ersten Start."""
    path = Path(path)
    if path.exists():
        raw = path.read_bytes()
        key = serialization.load_pem_private_key(raw, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"{path} ist kein Ed25519-Schlüssel")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        path.write_bytes(pem)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = b64u(hashlib.sha256(public).digest())[:16]
    return IssuerKey(private_key=key, key_id=key_id, public_key_b64=b64u(public))


def verify_document(document: dict[str, Any], public_key_b64: str) -> bool:
    """Prüft die Signatur eines Attestierungsdokuments."""
    signature = document.get("signature") or {}
    if signature.get("alg") != "Ed25519" or not signature.get("value"):
        return False
    try:
        key = Ed25519PublicKey.from_public_bytes(b64u_decode(public_key_b64))
        key.verify(b64u_decode(signature["value"]), canonical_bytes(document))
        return True
    except Exception:
        return False
