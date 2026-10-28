"""FastAPI-Installation der PayAPI-Instanz (unabhängig von /api/attest)."""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from attest.billing import record_invoice
from attest.discovery import OUTPUT_SCHEMA, atomic_amount
from attest.models import Observation
from attest.plausibility import check_observation
from attest.signing import IssuerKey, load_or_create_key, verify_document
from attest.x402_gate import build_payment_middleware, facilitator_supports

from .config import PayAPIConfig, load

PAYAPI_PATH = "/api/attest-v2"
SERVICE = "Reise-Agent Attest v2 (PayAPI)"
DESCRIPTION = (
    "Ed25519-signierte Preis-Attestierung für Reiseangebote (Flüge, Hotels, "
    "Fähren, Kreuzfahrten) mit Plausibilitätsprüfung. Pay-per-Call über x402 v2 "
    "auf Base; die Beobachtung liefert der Käufer."
)
logger = logging.getLogger("attest.payapi")

public_router = APIRouter()
paid_router = APIRouter()

_cfg: PayAPIConfig | None = None
_issuer: IssuerKey | None = None


def config() -> PayAPIConfig:
    global _cfg
    if _cfg is None:
        _cfg = load()
    return _cfg


def issuer() -> IssuerKey:
    global _issuer
    if _issuer is None:
        _issuer = load_or_create_key(config().settings.key_file)
    return _issuer


def _base_url(request: Request) -> str:
    return config().settings.public_base_url or str(request.base_url).rstrip("/")


def _public_key_doc() -> dict[str, Any]:
    key = issuer()
    return {
        "did": config().settings.issuer_did,
        "key_id": key.key_id,
        "alg": "Ed25519",
        "public_key": key.public_key_b64,
    }


def _reference_observation(note: str | None = None) -> dict[str, Any]:
    """Signierbares Referenzbeispiel für den PayAPI-Canary (GET ohne Body)."""
    return {
        "route": "BER-FCO",
        "travel_date": (date.today() + timedelta(days=7)).isoformat(),
        "price": "129.99",
        "currency": "EUR",
        "price_scope": "per_person",
        "source": "payapi-reference",
        "source_url": "https://payapi.market",
        "passengers": 1,
        "note": note or (
            "Signiertes Referenzbeispiel für den PayAPI-Canary. Für eine "
            "Attestierung eigener Daten POST mit route/travel_date/price/source."
        ),
    }


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
    s = config().settings
    now = datetime.now(timezone.utc)
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
        "observed_at": observed.isoformat().replace("+00:00", "Z"),
        "note": obs.note,
    }
    return {
        "version": "1",
        "service": SERVICE,
        "instance": config().instance,
        "id": f"att_{uuid.uuid4().hex}",
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(seconds=s.ttl_seconds)).isoformat().replace("+00:00", "Z"),
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
            "verification": f"{PAYAPI_PATH}/verify",
        },
    }


def _sign(obs: Observation, request: Request) -> dict[str, Any]:
    plausibility = check_observation(obs, ttl_seconds=config().settings.ttl_seconds)
    if plausibility.get("status") == "reject":
        raise ValueError("Plausibilitätsprüfung fehlgeschlagen")
    document = issuer().sign(_build_document(obs, plausibility, _payer_from_state(request)))
    request.state.attestation = document
    return document


def _observation_from_query(request: Request) -> Observation:
    q = request.query_params
    fields = {
        "route": q.get("route"),
        "travel_date": q.get("travel_date"),
        "price": q.get("price"),
        "currency": q.get("currency"),
        "price_scope": q.get("price_scope"),
        "source": q.get("source"),
        "source_url": q.get("source_url"),
        "passengers": q.get("passengers"),
    }
    provided = {k: v for k, v in fields.items() if v not in (None, "")}
    if not provided:
        return Observation.model_validate(_reference_observation())
    data = _reference_observation()
    data.update(provided)
    try:
        return Observation.model_validate(data)
    except Exception:  # noqa: BLE001
        return Observation.model_validate(_reference_observation(
            "Ungültige Query-Parameter; signiertes Referenzbeispiel zurückgegeben."
        ))


def _observation_from_body(body: Any) -> Observation:
    if not isinstance(body, dict) or not body:
        return Observation.model_validate(_reference_observation())
    try:
        return Observation.model_validate(body)
    except Exception:  # noqa: BLE001
        return Observation.model_validate(_reference_observation(
            "Ungültiger Request-Body; signiertes Referenzbeispiel zurückgegeben."
        ))


# ------------------------------------------------------------------ free routes
@public_router.get("/api/attest-v2/key")
async def payapi_key() -> JSONResponse:
    return JSONResponse(_public_key_doc())


@public_router.post("/api/attest-v2/validate")
async def payapi_validate(request: Request) -> JSONResponse:
    try:
        obs = Observation.model_validate(await request.json())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=422)
    plausibility = check_observation(obs, ttl_seconds=config().settings.ttl_seconds)
    ok = plausibility.get("status") != "reject"
    return JSONResponse(
        {
            "valid": ok,
            "plausibility": plausibility,
            "price": config().settings.price,
            "network": config().settings.network,
            "instance": config().instance,
        },
        status_code=200 if ok else 422,
    )


@public_router.post("/api/attest-v2/verify")
async def payapi_verify(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"valid": False, "error": "JSON erwartet"}, status_code=400)
    document = body.get("document") if isinstance(body, dict) else None
    public_key = (body.get("public_key") if isinstance(body, dict) else None) \
        or _public_key_doc()["public_key"]
    if not isinstance(document, dict):
        return JSONResponse({"valid": False, "error": "document fehlt"}, status_code=400)
    return JSONResponse({
        "valid": verify_document(document, public_key),
        "key_id": (document.get("signature") or {}).get("key_id"),
        "issuer": (document.get("issuer") or {}).get("did"),
    })


def _manifest(request: Request) -> dict[str, Any]:
    s = config().settings
    return {
        "x402Version": 2,
        "resources": [{
            "url": f"{_base_url(request)}{PAYAPI_PATH}",
            "description": DESCRIPTION,
            "serviceName": SERVICE,
            "accepts": [{
                "scheme": "exact",
                "network": s.network,
                "payTo": s.pay_to,
                "asset": s.resolved_asset(),
                "amount": atomic_amount(s.price),
                "maxTimeoutSeconds": s.max_timeout_seconds,
                "extra": {"name": config().extra_name, "version": "2"},
            }],
            "outputSchema": OUTPUT_SCHEMA,
            "tags": ["travel", "price", "attestation", "payapi"],
        }],
    }


@public_router.get("/.well-known/x402")
async def payapi_manifest(request: Request) -> JSONResponse:
    return JSONResponse(_manifest(request))


@public_router.get("/api/attest-v2/openapi.json")
async def payapi_openapi(request: Request) -> JSONResponse:
    base = _base_url(request)
    return JSONResponse({
        "openapi": "3.1.0",
        "info": {"title": SERVICE, "version": "1.0.0",
                 "description": DESCRIPTION},
        "servers": [{"url": base}],
        "paths": {
            PAYAPI_PATH: {
                "get": {
                    "summary": "Signed reference attestation (paid)",
                    "parameters": [
                        {"name": "route", "in": "query", "schema": {"type": "string"}},
                        {"name": "travel_date", "in": "query", "schema": {"type": "string", "format": "date"}},
                        {"name": "price", "in": "query", "schema": {"type": "string"}},
                        {"name": "source", "in": "query", "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"description": "Signed attestation"},
                                  "402": {"description": "Payment required"}},
                },
                "post": {
                    "summary": "Signed attestation of a submitted observation (paid)",
                    "requestBody": {"required": False,
                                    "content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "Signed attestation"},
                                  "402": {"description": "Payment required"}},
                },
            },
            f"{PAYAPI_PATH}/key": {"get": {"responses": {"200": {"description": "Public key"}}}},
            f"{PAYAPI_PATH}/validate": {"post": {"responses": {"200": {"description": "Validation"}}}},
            f"{PAYAPI_PATH}/verify": {"post": {"responses": {"200": {"description": "Verification"}}}},
            "/.well-known/x402": {"get": {"responses": {"200": {"description": "x402 manifest"}}}},
        },
    })


# ------------------------------------------------------------------ paid routes
@paid_router.api_route(PAYAPI_PATH, methods=["GET", "HEAD"])
async def payapi_get(request: Request) -> JSONResponse:
    try:
        document = _sign(_observation_from_query(request), request)
    except ValueError as exc:
        return JSONResponse(
            {"error": str(exc),
             "hint": "GET ohne Query-Parameter liefert ein signiertes Referenzbeispiel."},
            status_code=422,
        )
    return JSONResponse(document, headers=_attestation_headers(document))


@paid_router.post(PAYAPI_PATH)
async def payapi_post(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        document = _sign(_observation_from_body(body), request)
    except ValueError as exc:
        return JSONResponse(
            {"error": str(exc),
             "hint": "Leerer Body oder GET ohne Parameter liefert ein signiertes Referenzbeispiel."},
            status_code=422,
        )
    return JSONResponse(document, headers=_attestation_headers(document))


def _attestation_headers(document: dict[str, Any]) -> dict[str, str]:
    return {
        "X-Attestation-Id": document["id"],
        "X-Attestation-Key-Id": document["issuer"]["key_id"],
        "Link": '</.well-known/x402>; rel="payment-discovery"',
    }


async def _billing_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path != PAYAPI_PATH or response.status_code != 200:
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
        record_invoice(document, settlement, path=config().ledger, service=SERVICE)
    except Exception:  # noqa: BLE001
        logger.exception("PayAPI-Rechnung konnte nicht geschrieben werden")
    return response


def install(app) -> bool:
    """Hängt die zweite Instanz an die bestehende FastAPI-App."""
    global _cfg
    cfg = load()
    _cfg = cfg
    if not cfg.enabled:
        logger.info("PayAPI-Instanz deaktiviert (enabled=false)")
        return False

    s = cfg.settings
    auth = s.facilitator.auth
    if auth.mode == "cdp_jwt" and not (
        os.environ.get(auth.key_id_env) and os.environ.get(auth.key_secret_env)
    ):
        detail = (
            f"CDP-Credentials fehlen ({auth.key_id_env}/{auth.key_secret_env}); "
            "PayAPI-Instanz wird nicht aktiviert."
        )
        logger.warning(detail)

        @app.api_route(PAYAPI_PATH, methods=["GET", "HEAD", "POST"])
        async def _unavailable() -> JSONResponse:
            return JSONResponse(
                {"error": "Zahlungsweg nicht verfügbar", "detail": detail},
                status_code=503,
            )

        return False

    ok, detail = facilitator_supports(s)
    if not ok:
        logger.error("PayAPI-x402 deaktiviert: %s", detail)

        @app.api_route(PAYAPI_PATH, methods=["GET", "HEAD", "POST"])
        async def _unavailable() -> JSONResponse:
            return JSONResponse(
                {"error": "Zahlungsweg nicht verfügbar", "detail": detail},
                status_code=503,
            )

        return False

    app.include_router(public_router)

    try:
        middleware = build_payment_middleware(
            s,
            path=PAYAPI_PATH,
            service_name=SERVICE,
            description=DESCRIPTION,
            tags=["travel", "price", "attestation", "payapi"],
            include_bazaar=True,
            extra={"name": cfg.extra_name, "version": "2"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("PayAPI-Middleware nicht verfügbar: %s", exc)

        @app.api_route(PAYAPI_PATH, methods=["GET", "HEAD", "POST"])
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
        "PayAPI-Instanz aktiv: path=%s network=%s payTo=%s price=%s extra=%s",
        PAYAPI_PATH, s.network, s.pay_to, s.price, cfg.extra_name,
    )
    return True
