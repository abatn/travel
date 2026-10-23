"""Facilitator-Authentifizierung – konfigurationsgetrieben.

Unterstützt:
  * `none`    – OpenFacilitator / x402.org (kein Account)
  * `bearer`  – statischer Token (z. B. selbst gehosteter Facilitator)
  * `cdp_jwt` – Coinbase CDP: JWT pro Endpoint (ES256 oder EdDSA)

Der Aufrufer (x402-Middleware) ruft `create_headers()` vor jedem Request auf
und bekommt fertige Header für `verify`, `settle` und `supported`.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import time
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from .config import AuthSettings


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _load_private_key(secret: str):
    """Lädt einen CDP-Secret (base64 oder PEM) als Schlüsselobjekt."""
    text = secret.strip()
    if "BEGIN" in text:
        return serialization.load_pem_private_key(text.encode(), password=None)

    try:
        raw = base64.b64decode(text, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("CDP-Secret ist weder PEM noch gültiges Base64") from exc

    if b"BEGIN" in raw:
        return serialization.load_pem_private_key(raw, password=None)
    if len(raw) == 32:
        return ed25519.Ed25519PrivateKey.from_private_bytes(raw)
    if len(raw) == 64:
        return ed25519.Ed25519PrivateKey.from_private_bytes(raw[:32])
    raise ValueError(
        "CDP-Secret konnte nicht gelesen werden (erwartet PEM, 32/64 Byte oder Base64 davon)"
    )


def _jwt(key, key_id: str, uri: str, alg: str) -> str:
    now = int(time.time())
    header = {"alg": alg, "kid": key_id, "typ": "JWT", "nonce": secrets.token_hex(8)}
    payload = {
        "sub": key_id,
        "iss": "cdp",
        "nbf": now,
        "exp": now + 120,
        "uri": uri,
    }
    signing_input = (
        _b64u(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64u(json.dumps(payload, separators=(",", ":")).encode())
    ).encode("ascii")

    if alg == "EdDSA":
        signature = key.sign(signing_input)
    else:  # ES256
        der = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return signing_input.decode("ascii") + "." + _b64u(signature)


def _cdp_headers(auth: AuthSettings, base_url: str) -> dict[str, dict[str, str]]:
    key_id = os.environ.get(auth.key_id_env, "").strip()
    secret = os.environ.get(auth.key_secret_env, "").strip()
    if not key_id or not secret:
        raise RuntimeError(
            f"CDP-Auth aktiv, aber {auth.key_id_env} / {auth.key_secret_env} fehlen"
        )
    key = _load_private_key(secret)

    if auth.alg == "auto":
        alg = "EdDSA" if isinstance(key, ed25519.Ed25519PrivateKey) else "ES256"
    else:
        alg = auth.alg

    parsed = urlparse(base_url.rstrip("/"))
    host = parsed.netloc
    base_path = parsed.path.rstrip("/")
    headers: dict[str, dict[str, str]] = {}
    for endpoint in ("verify", "settle", "supported"):
        path = f"{base_path}/{endpoint}"
        token = _jwt(key, key_id, f"POST {host}{path}", alg)
        headers[endpoint] = {"Authorization": f"Bearer {token}"}
    # /supported ist ein GET; CDP bindet die Methode in `uri`.
    headers["supported"] = {
        "Authorization": "Bearer " + _jwt(key, key_id, f"GET {host}{base_path}/supported", alg)
    }
    return headers


def build_auth_headers(auth: AuthSettings, base_url: str):
    """Liefert ein `create_headers`-Callable oder None (keine Auth)."""
    mode = (auth.mode or "none").lower()
    if mode in ("none", "off", ""):
        return None
    if mode == "bearer":
        token = os.environ.get(auth.token_env, "").strip()
        if not token:
            raise RuntimeError(f"Bearer-Auth aktiv, aber {auth.token_env} fehlt")
        header = {"Authorization": f"Bearer {token}"}
        return lambda: {ep: dict(header) for ep in ("verify", "settle", "supported")}
    if mode == "cdp_jwt":
        return lambda: _cdp_headers(auth, base_url)
    raise ValueError(f"Unbekannter Auth-Modus: {auth.mode}")
