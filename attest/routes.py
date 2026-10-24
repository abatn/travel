"""FastAPI-Routen für Attestierungen, Discovery und Verifikation.

Bezahlte Route:  POST /api/attest        (x402, exact, konfigurierbares Netz)
Frei:            POST /api/attest/validate
                 POST /api/attest/verify
                 GET  /api/attest/key
                 GET  /.well-known/agent-payments.json
"""
from __future__ import annotations

import logging
import re
import uuid
import base64
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .billing import record_invoice
from .capabilities import capabilities_document
from .config import Settings, load_settings
from .discovery import SAMPLE_INPUT, SAMPLE_OUTPUT, atomic_amount, bazaar_extension, contact_email
try:
    from ui.i18n_core import (SUPPORTED as I18N_SUPPORTED, t as i18n_t,
                              resolve as i18n_resolve)
except ModuleNotFoundError:  # Fallback: keine Übersetzungen, kein Absturz
    try:
        from i18n import SUPPORTED as I18N_SUPPORTED, t as i18n_t

        def i18n_resolve(request):
            return "de"
    except ModuleNotFoundError:
        I18N_SUPPORTED = ("de",)

        def i18n_t(lang, key, default=None, **params):
            return default if default is not None else key

        def i18n_resolve(request):
            return "de"
from .models import Observation
from .plausibility import check_observation
from .signing import IssuerKey, load_or_create_key, verify_document
from .x402_gate import ATTEST_PATH, build_payment_middleware, describe, facilitator_supports

logger = logging.getLogger("attest")
ROOT = Path(__file__).resolve().parents[1]

public_router = APIRouter()
paid_router = APIRouter()
_settings: Settings | None = None
_issuer: IssuerKey | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _price_parts(price: str) -> tuple[str, str]:
    value = price.strip()
    currency = "USD"
    if value.startswith("€"):
        currency, value = "EUR", value[1:]
    elif value.startswith("$"):
        value = value[1:]
    elif value.upper().startswith("USD"):
        value = value[3:]
    elif value.upper().startswith("EUR"):
        currency, value = "EUR", value[3:]
    value = value.strip()
    try:
        amount = format(Decimal(value), "f")
    except Exception:
        amount = value
    return amount, currency


def settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def issuer() -> IssuerKey:
    global _issuer
    if _issuer is None:
        _issuer = load_or_create_key(settings().key_file)
    return _issuer


def _base_url(request: Request) -> str:
    return settings().public_base_url or str(request.base_url).rstrip("/")


def _public_key_doc() -> dict[str, Any]:
    key = issuer()
    return {"did": settings().issuer_did, "key_id": key.key_id,
            "alg": "Ed25519", "public_key": key.public_key_b64}


def _payer_from_state(request: Request) -> dict[str, Any]:
    payload = getattr(request.state, "payment_payload", None)
    if payload is not None and hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    requirements = getattr(request.state, "payment_requirements", None)
    if requirements is not None and hasattr(requirements, "model_dump"):
        requirements = requirements.model_dump()

    if not isinstance(payload, dict):
        payload = {}
    if not isinstance(requirements, dict):
        requirements = {}

    authorization = ((payload.get("payload") or {}).get("authorization") or {})
    accepted = payload.get("accepted") or {}
    if not isinstance(accepted, dict):
        accepted = {}
    return {
        "payer": authorization.get("from"),
        "network": accepted.get("network") or requirements.get("network"),
        "scheme": accepted.get("scheme") or requirements.get("scheme"),
        "asset": accepted.get("asset") or requirements.get("asset"),
        "amount": accepted.get("amount") or requirements.get("amount"),
        "x402_version": payload.get("x402_version") or payload.get("x402Version"),
    }


def _build_document(obs: Observation, plausibility: dict[str, Any],
                    payment: dict[str, Any]) -> dict[str, Any]:
    s = settings()
    now = _now()
    observed = obs.observed_at or now
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)

    subject = {
        "route": obs.route,
        "travel_date": obs.travel_date.isoformat(),
        "price": format(obs.price, "f"),
        "currency": obs.currency,
        "price_scope": obs.price_scope,
        "passengers": obs.passengers,
        "cabin": obs.cabin,
        "source": obs.source,
        "source_url": obs.source_url,
        "observed_at": _iso(observed),
        "note": obs.note,
    }
    return {
        "version": "1",
        "id": f"att_{uuid.uuid4().hex}",
        "issued_at": _iso(now),
        "expires_at": _iso(now + timedelta(seconds=s.ttl_seconds)),
        "issuer": {
            "did": s.issuer_did,
            "key_id": issuer().key_id,
            "public_key": issuer().public_key_b64,
            "alg": "Ed25519",
            "pay_to": s.pay_to,
        },
        "subject": subject,
        "plausibility": plausibility,
        "payment": payment,
        "terms": {
            "meaning": "Beobachtung, keine Buchungsgarantie und keine Preisgarantie.",
            "verification": "/api/attest/verify",
        },
    }


# --------------------------------------------------------------------------- public
def discovery_document(base: str, lang: str = "de") -> dict[str, Any]:
    """Erweitertes Discovery-Dokument inkl. x402-Bazaar-Feldern.

    ``name``/``description`` folgen der angefragten Sprache (Fallback Deutsch);
    die vollständige Übersicht bleibt in ``description_i18n``.
    """
    s = settings()
    code = lang if lang in I18N_SUPPORTED else "de"
    amount, currency = _price_parts(s.price)
    atomic = atomic_amount(amount)
    email = contact_email()
    issuer = _public_key_doc()
    resource_url = f"{base}{ATTEST_PATH}"

    resource = {
        "resource": resource_url,
        "type": "http",
        "x402Version": 2,
        "method": "POST",
        "description": i18n_t(
            code, "discovery.attest_description",
            default=("Signierte Preis-Attestierung: Route, Datum, Preis, Quelle, "
                     "Zeitstempel und Plausibilitätsprüfung (Ed25519)."),
        ),
        "mimeType": "application/json",
        "accepts": [{
            "scheme": "exact",
            "network": s.network,
            "asset": s.resolved_asset(),
            "amount": atomic,
            "payTo": s.pay_to,
            "maxTimeoutSeconds": s.max_timeout_seconds,
            "extra": {"name": "USDC" if s.testnet else "USD Coin", "version": "2"},
        }],
        "extensions": {"bazaar": bazaar_extension()},
    }

    return {
        "version": "1",
        "name": i18n_t(code, "discovery.name",
                       default="Reise-Agent Preis-Attestierungen"),
        "description": i18n_t(
            code, "discovery.description",
            default=("Signierte, mit Quelle und Zeitstempel versehene Preisbeobachtungen "
                     "für Reisestrecken. Für autonome Agenten gedacht; Zahlung per x402."),
        ),
        "provider": {
            "name": "Reise-Agent",
            "url": base,
            "contact": {"email": email or None, "url": f"{base}/impressum"},
        },
        "documentation": f"{base}/llms.txt",
        "terms": f"{base}/impressum",
        "privacy": f"{base}/datenschutz",
        "issuer": issuer,
        "endpoints": {
            "attest": {
                "method": "POST",
                "url": resource_url,
                "content_type": "application/json",
                "payment_required": True,
            },
            "validate": {
                "method": "POST",
                "url": f"{base}/api/attest/validate",
                "payment_required": False,
            },
            "verify": {
                "method": "POST",
                "url": f"{base}/api/attest/verify",
                "payment_required": False,
            },
            "key": {
                "method": "GET",
                "url": f"{base}/api/attest/key",
                "payment_required": False,
            },
            "register": {
                "method": "POST",
                "url": f"{base}/api/register",
                "payment_required": False,
            },
        },
        "resources": [resource],
        "payment": {
            **describe(s),
            "price": {
                "amount": amount,
                "amount_atomic": atomic,
                "currency": currency,
                "asset_symbol": "USDC",
            },
        },
        "capabilities": [
            "price_attestation",
            "plausibility_check",
            "source_provenance",
            "ed25519_signature",
            "ttl_freshness",
        ],
        "schema": {
            "request": SAMPLE_INPUT,
            "response": SAMPLE_OUTPUT,
        },
        "limits": {
            "ttl_seconds": s.ttl_seconds,
            "max_price": "100000",
            "rate_limit": "no hard limit; x402 payment per call",
            "refund_policy": "keine Rückerstattung nach Settlement (kein Chargeback)",
        },
        "contact": {"email": email or None, "url": f"{base}/impressum"},
        "languages": list(I18N_SUPPORTED),
        "description_i18n": {c: i18n_t(c, "discovery.description") for c in I18N_SUPPORTED},
        "serviceName_i18n": {c: i18n_t(c, "nav.pricing") for c in I18N_SUPPORTED},
        "lastUpdated": _iso(_now()),
    }


@public_router.get("/.well-known/agent-payments.json")
async def agent_payments(request: Request) -> JSONResponse:
    lang = getattr(request.state, "lang", None)
    if lang not in I18N_SUPPORTED:
        lang = i18n_resolve(request)
    return JSONResponse(discovery_document(_base_url(request), lang),
                        headers={"Cache-Control": "public, max-age=60"})


@public_router.get("/.well-known/capabilities.json")
async def capabilities_json(request: Request) -> JSONResponse:
    """Maschinenlesbarer Capability-Katalog (M3), kostenlos."""
    return JSONResponse(capabilities_document(load_settings(), _base_url(request)),
                        headers={"Cache-Control": "public, max-age=60"})


@public_router.get("/capabilities")
async def capabilities_page(request: Request) -> JSONResponse:
    """Derselbe Katalog unter kurzer URL."""
    return JSONResponse(capabilities_document(load_settings(), _base_url(request)),
                        headers={"Cache-Control": "public, max-age=60"})


@public_router.post("/api/register")
async def register_discovery(request: Request) -> JSONResponse:
    """Simuliert die Aufnahme in Discovery-Verzeichnisse und liefert die Payload.

    Es wird bewusst KEIN externer Dienst aufgerufen: Die Aufnahme ist bei den
    meisten Indexern manuell bzw. erfolgt nach einem erfolgreichen bezahlten Call.
    """
    base = _base_url(request)
    doc = discovery_document(base)
    payload = {
        "resource": doc["resources"][0],
        "provider": doc["provider"],
        "contact": doc["contact"],
        "documentation": doc["documentation"],
    }
    saved = ROOT / "attest" / "state" / "registration_request.json"
    try:
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:  # noqa: BLE001
        logger.warning("Registrierungs-Payload nicht gespeichert: %s", exc)

    return JSONResponse({
        "status": "simulated",
        "message": (
            "Kein automatischer Eintrag. Die Payload ist gespeichert und kann bei "
            "Discovery-Diensten eingereicht werden."
        ),
        "payload": payload,
        "saved_to": str(saved),
        "targets": [
            {
                "name": "Coinbase CDP Bazaar (Hauptindex)",
                "url": "https://api.cdp.coinbase.com/platform/v2/x402/discovery/search",
                "mode": "automatisch – keine Registrierung",
                "note": "Der Facilitator katalogisiert die Ressource nach dem ersten "
                        "erfolgreichen Settlement (paymentPayload.resource muss gesetzt "
                        "sein). Status prüfen: /v2/x402/validate – returns_402 muss true "
                        "sein (GET/HEAD müssen 402 antworten).",
            },
            {
                "name": "x402.new / x402scan / agentic.market (spiegeln CDP)",
                "url": "https://x402.new/submit",
                "mode": "automatisch (Index zieht CDP-Bazaar)",
                "note": "Kein Formular; erscheint in der Regel innerhalb einer Stunde "
                        "nach Katalogisierung im CDP-Bazaar.",
            },
            {
                "name": "Manuelle Verzeichnisse",
                "url": "https://github.com/xpaysh/awesome-x402",
                "mode": "Pull Request / Einreichung",
                "note": "PR bei xpaysh/awesome-x402, Rug-Munch/awesome-x402, x402.eco "
                        "(data/ecosystem/services-endpoints/), gold-402, "
                        "agent-tools.cloud (Formular) und x402-index (GitHub-Issue). "
                        "gold-402 verlangt eine lebende 402 auf GET.",
            },
            {
                "name": "Eigene Discovery",
                "url": f"{base}/.well-known/agent-payments.json",
                "mode": "bereits aktiv",
                "note": "Agenten können Preis, Netz, Asset, payTo und Endpunkte direkt lesen.",
            },
        ],
        "manual_steps": [
            "Ersten bezahlten Aufruf von POST /api/attest über den CDP-Facilitator "
            "durchführen (bewiesen: Tx 0x335fac… bzw. 0x2a848c… auf Base).",
            "GET/HEAD /api/attest müssen 402 antworten – sonst schlägt der offizielle "
            "Check POST /v2/x402/validate (returns_402) fehl und Verzeichnisse lehnen ab.",
            "Index-Eintrag prüfen: /v2/x402/discovery/search?query=hanibal.",
            "PRs/Issues an die manuellen Verzeichnisse senden (awesome-x402, x402.eco, "
            "gold-402, agent-tools.cloud, x402-index).",
            "30-Tage-Regel: Der CDP-Index blendet Ressourcen ohne Aktivität nach 30 "
            "Tagen aus – mindestens einmal monatlich selbst zahlen.",
            "llms.txt und /.well-known/agent-payments.json nach Änderungen aktualisieren.",
        ],
    })


@public_router.get("/api/attest/key")
async def attest_key() -> JSONResponse:
    return JSONResponse(_public_key_doc())


@public_router.post("/api/attest/validate")
async def attest_validate(request: Request) -> JSONResponse:
    try:
        obs = Observation.model_validate(await request.json())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=422)
    plausibility = check_observation(obs, ttl_seconds=settings().ttl_seconds)
    return JSONResponse(
        {
            "valid": plausibility["status"] != "reject",
            "plausibility": plausibility,
            "price": settings().price,
            "network": settings().network,
        },
        status_code=200 if plausibility["status"] != "reject" else 422,
    )


@public_router.post("/api/attest/verify")
async def attest_verify(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"valid": False, "error": "JSON erwartet"}, status_code=400)
    document = body.get("document") if isinstance(body, dict) else None
    public_key = (body.get("public_key") if isinstance(body, dict) else None) \
        or _public_key_doc()["public_key"]
    if not isinstance(document, dict):
        return JSONResponse({"valid": False, "error": "document fehlt"}, status_code=400)
    valid = verify_document(document, public_key)
    return JSONResponse({
        "valid": valid,
        "key_id": (document.get("signature") or {}).get("key_id"),
        "issuer": (document.get("issuer") or {}).get("did"),
    })


# --------------------------------------------------------------------------- paid
@paid_router.get(ATTEST_PATH)
async def attest_info() -> JSONResponse:
    """Hinweis für Verzeichnis-Prüfungen (GET/HEAD).

    Unbezahlte GET/HEAD-Anfragen werden schon von der x402-Middleware mit 402
    abgefangen – erst mit gültiger Zahlung erreicht diese Route der Agent und
    bekommt eine kurze Bedienhilfe (Attestierung selbst läuft über POST).
    """
    return JSONResponse({
        "detail": "Diese Route ist per Zahlung erreichbar; die Attestierung "
                  "selbst erfolgt über POST.",
        "post": ATTEST_PATH,
        "validate": f"{ATTEST_PATH}/validate",
        "verify": f"{ATTEST_PATH}/verify",
        "discovery": "/.well-known/agent-payments.json",
        "documentation": "/llms.txt",
    })


@paid_router.post(ATTEST_PATH)
async def attest(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "JSON erwartet"}, status_code=400)
    try:
        obs = Observation.model_validate(body)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"error": "ungültige Beobachtung", "detail": str(exc),
             "hint": "Vorab kostenlos prüfen: POST /api/attest/validate"},
            status_code=422,
        )

    plausibility = check_observation(obs, ttl_seconds=settings().ttl_seconds)
    if plausibility["status"] == "reject":
        return JSONResponse(
            {"error": "Plausibilitätsprüfung fehlgeschlagen",
             "plausibility": plausibility,
             "hint": "Vorab kostenlos prüfen: POST /api/attest/validate"},
            status_code=422,
        )

    payment = _payer_from_state(request)
    document = issuer().sign(_build_document(obs, plausibility, payment))
    request.state.attestation = document
    return JSONResponse(
        document,
        headers={
            "X-Attestation-Id": document["id"],
            "X-Attestation-Key-Id": document["issuer"]["key_id"],
            "Link": '</.well-known/agent-payments.json>; rel="payment-discovery"',
        },
    )


async def _billing_middleware(request: Request, call_next):
    """Schreibt nach erfolgreichem Settlement eine Rechnung (idempotent)."""
    response = await call_next(request)
    if request.url.path != ATTEST_PATH or response.status_code != 200:
        return response
    document = getattr(request.state, "attestation", None)
    if not document:
        return response
    header = (response.headers.get("payment-response")
              or response.headers.get("x-payment-response"))
    settlement: dict[str, Any] = {}
    if header:
        try:
            settlement = json.loads(
                base64.b64decode(header + "=" * (-len(header) % 4)).decode("utf-8")
            )
        except Exception:  # noqa: BLE001
            settlement = {}
    try:
        record_invoice(document, settlement)
    except Exception:  # noqa: BLE001
        logger.exception("Rechnung konnte nicht geschrieben werden")
    return response


def install(app) -> bool:
    """Hängt Discovery + bezahlte Route an eine FastAPI-App."""
    global _settings
    s = load_settings()
    _settings = s
    if not s.enabled:
        logger.info("Attestierung deaktiviert (attest.enabled=false)")
        return False

    app.include_router(public_router)
    ok, detail = facilitator_supports(s)
    if not ok:
        logger.error("x402 deaktiviert: %s", detail)

        @app.api_route(ATTEST_PATH, methods=["GET", "HEAD", "POST"])
        async def _unavailable() -> JSONResponse:
            return JSONResponse(
                {"error": "Zahlungsweg nicht verfügbar", "detail": detail},
                status_code=503,
            )

        return False
    try:
        middleware = build_payment_middleware(s)
    except Exception as exc:  # noqa: BLE001
        logger.error("x402-Middleware nicht verfügbar: %s", exc)

        @app.api_route(ATTEST_PATH, methods=["GET", "HEAD", "POST"])
        async def _unavailable() -> JSONResponse:
            return JSONResponse(
                {"error": "Zahlungsweg nicht verfügbar", "detail": str(exc)},
                status_code=503,
            )

        return False

    app.middleware("http")(middleware)
    app.middleware("http")(_billing_middleware)
    app.include_router(paid_router)
    logger.info(
        "Attestierung aktiv: network=%s facilitator=%s auth=%s payTo=%s",
        s.network, s.facilitator.url, s.facilitator.auth.mode, s.pay_to,
    )
    return True
