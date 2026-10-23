"""Konfiguration: YAML + Umgebungsvariablen, ohne Code-Wechsel beim Facilitator.

Priorität: Umgebungsvariable > YAML > Default.

Der entscheidende Punkt für den späteren Wechsel:
  * `payment.network` (CAIP-2)
  * `payment.facilitator.url`
  * `payment.facilitator.auth` (none | bearer | cdp_jwt)
Alles andere (Preis, payTo, Asset) ist ebenfalls Konfiguration.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_CONFIG = HERE / "config.yaml"


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value is not None and value.strip() != "" else None


def _env_bool(name: str) -> bool | None:
    value = _env(name)
    if value is None:
        return None
    return value.lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class AuthSettings:
    mode: str = "none"                 # none | bearer | cdp_jwt
    token_env: str = "X402_FACILITATOR_TOKEN"
    key_id_env: str = "CDP_API_KEY_ID"
    key_secret_env: str = "CDP_API_KEY_SECRET"
    alg: str = "auto"                  # auto | ES256 | EdDSA


@dataclass(frozen=True)
class FacilitatorSettings:
    url: str = "https://pay.openfacilitator.io"
    timeout: float = 30.0
    auth: AuthSettings = field(default_factory=AuthSettings)


@dataclass(frozen=True)
class Settings:
    enabled: bool = True
    network: str = "eip155:84532"
    pay_to: str = "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4"
    price: str = "$0.002"
    asset: str | None = None
    max_timeout_seconds: int = 120
    issuer_did: str = "did:web:localhost%3A8077"
    key_file: Path = ROOT / "attest/keys/issuer.ed25519"
    ttl_seconds: int = 300
    facilitator: FacilitatorSettings = field(default_factory=FacilitatorSettings)
    public_base_url: str = ""

    @property
    def testnet(self) -> bool:
        return self.network in ("eip155:84532", "base-sepolia")

    def resolved_asset(self) -> str:
        """Asset-Adresse: Konfiguration oder x402-Standardasset des Netzwerks."""
        if self.asset:
            return self.asset
        try:
            from x402.mechanisms.evm.default_assets import get_default_asset

            found = get_default_asset(self.network)
            if found and found.get("asset"):
                return str(found["asset"])
        except Exception:
            pass
        # Fallback: Base Sepolia / Base Mainnet USDC (Circle)
        return (
            "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
            if self.testnet
            else "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        )


def _section(data: dict[str, Any], *path: str) -> dict[str, Any]:
    node: Any = data
    for key in path:
        node = (node or {}).get(key, {})
        if not isinstance(node, dict):
            return {}
    return node


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    return loaded if isinstance(loaded, dict) else {}


def load_settings(path: str | Path | None = None) -> Settings:
    """Lädt YAML und wendet Env-Overrides an.

    `ATTEST_CONFIG` erlaubt eine alternative Datei (z. B. Test/Mainnet).
    """
    cfg_path = Path(path or _env("ATTEST_CONFIG") or DEFAULT_CONFIG)
    data = _read_yaml(cfg_path)

    issuer = _section(data, "issuer")
    payment = _section(data, "payment")
    fac = _section(data, "payment", "facilitator")
    auth = _section(data, "payment", "facilitator", "auth")

    key_file = Path(str(issuer.get("key_file", "attest/keys/issuer.ed25519")))
    if not key_file.is_absolute():
        key_file = ROOT / key_file

    settings = Settings(
        enabled=bool(data.get("enabled", True)),
        network=str(payment.get("network", "eip155:84532")),
        pay_to=str(payment.get("pay_to", "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4")),
        price=str(payment.get("price", "$0.002")),
        asset=(str(payment["asset"]) if payment.get("asset") else None),
        max_timeout_seconds=int(payment.get("max_timeout_seconds", 120)),
        issuer_did=str(issuer.get("did", "did:web:localhost%3A8077")),
        key_file=key_file,
        ttl_seconds=int(issuer.get("ttl_seconds", 300)),
        facilitator=FacilitatorSettings(
            url=str(fac.get("url", "https://pay.openfacilitator.io")),
            timeout=float(fac.get("timeout", 30)),
            auth=AuthSettings(
                mode=str(auth.get("mode", "none")).lower(),
                token_env=str(auth.get("token_env", "X402_FACILITATOR_TOKEN")),
                key_id_env=str(auth.get("key_id_env", "CDP_API_KEY_ID")),
                key_secret_env=str(auth.get("key_secret_env", "CDP_API_KEY_SECRET")),
                alg=str(auth.get("alg", "auto")),
            ),
        ),
        public_base_url=str(data.get("public_base_url", "")).rstrip("/"),
    )

    # ------------------------------------------------------------ Env-Overrides
    overrides: dict[str, Any] = {}
    if (v := _env_bool("ATTEST_ENABLED")) is not None:
        overrides["enabled"] = v
    if v := _env("ATTEST_NETWORK"):
        overrides["network"] = v
    if v := _env("ATTEST_PAY_TO"):
        overrides["pay_to"] = v
    if v := _env("ATTEST_PRICE"):
        overrides["price"] = v
    if v := _env("ATTEST_ASSET"):
        overrides["asset"] = v
    if v := _env("ATTEST_ISSUER_DID"):
        overrides["issuer_did"] = v
    if v := _env("ATTEST_KEY_FILE"):
        overrides["key_file"] = Path(v)
    if v := _env("ATTEST_PUBLIC_BASE_URL"):
        overrides["public_base_url"] = v

    fac_overrides: dict[str, Any] = {}
    if v := _env("ATTEST_FACILITATOR_URL"):
        fac_overrides["url"] = v
    if v := _env("ATTEST_FACILITATOR_TIMEOUT"):
        fac_overrides["timeout"] = float(v)

    auth_overrides: dict[str, Any] = {}
    if v := _env("ATTEST_FACILITATOR_AUTH"):
        auth_overrides["mode"] = v.lower()
    if v := _env("ATTEST_FACILITATOR_TOKEN_ENV"):
        auth_overrides["token_env"] = v
    if v := _env("CDP_API_KEY_ID"):
        auth_overrides.setdefault("key_id_env", "CDP_API_KEY_ID")
    if v := _env("ATTEST_CDP_ALG"):
        auth_overrides["alg"] = v

    if auth_overrides:
        fac_overrides["auth"] = replace(settings.facilitator.auth, **auth_overrides)
    if fac_overrides:
        overrides["facilitator"] = replace(settings.facilitator, **fac_overrides)
    if overrides:
        settings = replace(settings, **overrides)
    return settings
