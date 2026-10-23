"""x402-Gate: ein Middleware-Objekt, zwei Facilitatoren – nur Konfiguration.

OpenFacilitator (Base Sepolia, kostenlos):
    url: https://pay.openfacilitator.io
    auth.mode: none

Coinbase CDP (Mainnet):
    url: https://api.cdp.coinbase.com/platform/v2/x402
    auth.mode: cdp_jwt  (CDP_API_KEY_ID / CDP_API_KEY_SECRET)
"""
from __future__ import annotations

from typing import Any

import httpx
from x402 import x402ResourceServer
from x402.http import HTTPFacilitatorClient
from x402.http.middleware.fastapi import payment_middleware
from x402.mechanisms.evm.exact.server import ExactEvmScheme

from .auth import build_auth_headers
from .config import Settings
from .discovery import bazaar_extension

ATTEST_PATH = "/api/attest"


def facilitator_config(settings: Settings) -> dict[str, Any]:
    """Baut die Facilitator-Konfiguration – der einzige Unterschied ist Config."""
    config: dict[str, Any] = {
        "url": settings.facilitator.url,
        "timeout": settings.facilitator.timeout,
    }
    create_headers = build_auth_headers(settings.facilitator.auth, settings.facilitator.url)
    if create_headers is not None:
        config["create_headers"] = create_headers
    return config


def facilitator_supports(settings: Settings) -> tuple[bool, str]:
    """Prüft vor dem Bau der Middleware, ob der Facilitator unser Netz kann.

    Verhindert, dass ein falsch konfigurierter Facilitator den Prozess beim
    Start beendet (die x402-SDK behandelt Capability-Fehler als fatal).
    """
    url = settings.facilitator.url.rstrip("/") + "/supported"
    try:
        config = facilitator_config(settings)
        headers: dict[str, str] = {}
        factory = config.get("create_headers")
        if factory is not None:
            headers = (factory().get("supported") or {})
        response = httpx.get(url, headers=headers, timeout=settings.facilitator.timeout)
        response.raise_for_status()
        kinds = (response.json() or {}).get("kinds") or []
    except Exception as exc:  # noqa: BLE001
        return False, f"Facilitator nicht erreichbar ({url}): {exc}"

    networks = {str(k.get("network")) for k in kinds if isinstance(k, dict)}
    if settings.network not in networks:
        return False, (
            f"Facilitator {settings.facilitator.url} unterstützt {settings.network} nicht "
            f"(angeboten: {', '.join(sorted(networks)) or 'nichts'})"
        )
    return True, "ok"


def build_payment_middleware(settings: Settings):
    """Erzeugt die FastAPI-Middleware für POST /api/attest."""
    facilitator = HTTPFacilitatorClient(facilitator_config(settings))
    server = x402ResourceServer(facilitator)
    server.register(settings.network, ExactEvmScheme())

    accepts: dict[str, Any] = {
        "scheme": "exact",
        "network": settings.network,
        "payTo": settings.pay_to,
        "price": settings.price,
        "maxTimeoutSeconds": settings.max_timeout_seconds,
    }
    if settings.asset:
        accepts["asset"] = settings.asset

    routes: dict[str, Any] = {
        f"POST {ATTEST_PATH}": {
            "accepts": [accepts],
            "description": (
                "Signierte Preis-Attestierung: Route, Datum, Preis, Quelle, "
                "Zeitstempel und Plausibilitätsprüfung (Ed25519)."
            ),
            "mimeType": "application/json",
            "serviceName": "Reise-Agent Attest",
            "tags": ["travel", "price", "attestation", "x402"],
            "extensions": {"bazaar": bazaar_extension()},
        }
    }
    return payment_middleware(
        routes,
        server,
        paywall_config={"app_name": "Reise-Agent Preis-Attestierung"},
        sync_facilitator_on_start=True,
    )


def describe(settings: Settings) -> dict[str, Any]:
    """Maschinenlesbare Beschreibung des Zahlungswegs (für Discovery)."""
    return {
        "protocol": "x402",
        "version": 2,
        "scheme": "exact",
        "network": settings.network,
        "network_name": "base-sepolia" if settings.testnet else "base",
        "asset": settings.resolved_asset(),
        "pay_to": settings.pay_to,
        "price": settings.price,
        "facilitator": {
            "url": settings.facilitator.url,
            "auth": settings.facilitator.auth.mode,
        },
    }
