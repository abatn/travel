"""PayAPI-Konfiguration – bewusst getrennt von ``attest/config.yaml``.

Es werden nur ``PAYAPI_*``-Umgebungsvariablen gelesen. Die bestehende
M2-Instanz (``ATTEST_*``) kann die zweite Instanz damit nicht beeinflussen.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from attest.config import AuthSettings, FacilitatorSettings, Settings

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
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
class PayAPIConfig:
    settings: Settings
    ledger: Path
    instance: str
    extra_name: str

    @property
    def enabled(self) -> bool:
        return self.settings.enabled


def _section(data: dict[str, Any], *path: str) -> dict[str, Any]:
    node: Any = data
    for key in path:
        node = (node or {}).get(key, {})
        if not isinstance(node, dict):
            return {}
    return node


def _abs(path_value: str | Path, default: Path) -> Path:
    path = Path(str(path_value or default))
    return path if path.is_absolute() else ROOT / path


def load(path: str | Path | None = None) -> PayAPIConfig:
    cfg_path = Path(path or _env("PAYAPI_CONFIG") or DEFAULT_CONFIG)
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        data = {}

    issuer = _section(data, "issuer")
    payment = _section(data, "payment")
    fac = _section(data, "payment", "facilitator")
    auth = _section(data, "payment", "facilitator", "auth")
    extra = _section(data, "payment", "extra")

    key_file = _abs(issuer.get("key_file", ""), HERE / "keys" / "issuer.ed25519")
    ledger = _abs(data.get("ledger", ""), HERE / "state" / "invoices.jsonl")

    settings = Settings(
        enabled=bool(data.get("enabled", True)),
        network=str(payment.get("network", "eip155:8453")),
        pay_to=str(payment.get("pay_to", "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4")),
        price=str(payment.get("price", "$0.01")),
        asset=(str(payment["asset"]) if payment.get("asset") else None),
        max_timeout_seconds=int(payment.get("max_timeout_seconds", 120)),
        issuer_did=str(issuer.get("did", "did:web:travel.hanibal-ai.com:payapi")),
        key_file=key_file,
        ttl_seconds=int(issuer.get("ttl_seconds", 300)),
        facilitator=FacilitatorSettings(
            url=str(fac.get("url", "https://api.cdp.coinbase.com/platform/v2/x402")),
            timeout=float(fac.get("timeout", 30)),
            auth=AuthSettings(
                mode=str(auth.get("mode", "cdp_jwt")).lower(),
                token_env=str(auth.get("token_env", "X402_FACILITATOR_TOKEN")),
                key_id_env=str(auth.get("key_id_env", "CDP_API_KEY_ID")),
                key_secret_env=str(auth.get("key_secret_env", "CDP_API_KEY_SECRET")),
                alg=str(auth.get("alg", "auto")),
            ),
        ),
        public_base_url=str(data.get("public_base_url", "")).rstrip("/"),
    )

    # Nur PAYAPI_*-Overrides, damit die Hauptinstanz unabhängig bleibt.
    overrides: dict[str, Any] = {}
    if (v := _env_bool("PAYAPI_ENABLED")) is not None:
        overrides["enabled"] = v
    if v := _env("PAYAPI_NETWORK"):
        overrides["network"] = v
    if v := _env("PAYAPI_PAY_TO"):
        overrides["pay_to"] = v
    if v := _env("PAYAPI_PRICE"):
        overrides["price"] = v
    if v := _env("PAYAPI_KEY_FILE"):
        overrides["key_file"] = Path(v)
    if v := _env("PAYAPI_PUBLIC_BASE_URL"):
        overrides["public_base_url"] = v.rstrip("/")
    if v := _env("PAYAPI_FACILITATOR_URL"):
        overrides["facilitator"] = FacilitatorSettings(
            url=v,
            timeout=settings.facilitator.timeout,
            auth=settings.facilitator.auth,
        )
    if overrides:
        from dataclasses import replace

        settings = replace(settings, **overrides)

    return PayAPIConfig(
        settings=settings,
        ledger=Path(_env("PAYAPI_LEDGER")) if _env("PAYAPI_LEDGER") else ledger,
        instance=str(data.get("instance", "payapi-market")),
        extra_name=str(extra.get("name", "USD Coin")),
    )
