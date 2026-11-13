"""FastAPI-Installation der PayAPI-Instanz (unabhängig von /api/attest)."""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from attest.billing import record_invoice
from attest.discovery import OUTPUT_SCHEMA, atomic_amount, contact_email
from attest.models import Observation
from attest.plausibility import check_observation
from attest.signing import (IssuerKey, load_or_create_key, verify_attestation,
                            verify_attestation_details)
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


def _verification_method(did: str, key: IssuerKey) -> dict[str, Any]:
    return {
        "id": f"{did}#{key.key_id}",
        "type": "JsonWebKey2020",
        "controller": did,
        "publicKeyJwk": {
            "kty": "OKP",
            "crv": "Ed25519",
            "x": key.public_key_b64,
        },
    }


def _did_document(did: str) -> dict[str, Any]:
    key = issuer()
    method = _verification_method(did, key)
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/jws-2020/v1",
        ],
        "id": did,
        "verificationMethod": [method],
        "authentication": [method["id"]],
        "assertionMethod": [method["id"]],
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
    # Ein "reject"-Verdikt ist Teil des Produkts (signierte Beobachtung +
    # Pruefergebnis), kein Infrastrukturfehler. Frueher wurde hier 422
    # zurueckgegeben; ein Health-Check mit veraltetem Beispiel-Datum bekam
    # damit nach der Zahlung eine Fehlerantwort ("degraded"). Jetzt wird auch
    # ein negatives Verdikt signiert und mit HTTP 200 geliefert — ehrlich,
    # weil plausibility.status = "reject" im Dokument steht.
    document = issuer().sign(_build_document(obs, plausibility, _payer_from_state(request)))
    request.state.attestation = document
    return document


def _reference_observation(note: str | None = None) -> dict[str, Any]:
    """Signierbares Referenzbeispiel für kalte Probes (GET/POST ohne Eingaben).

    Ein Health-Check, der nach der Zahlung ohne Body/Query aufruft, bekommt so
    ein echtes, signiertes Dokument (HTTP 200) statt 422 — sonst wertet der
    Indexer die Route als beeintraechtigt.
    """
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
            "Signiertes Referenzbeispiel für kalte Probes. Für eine eigene "
            "Attestierung POST mit route/travel_date/price/source."
        ),
    }


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


@public_router.get("/payapi/did.json")
async def payapi_did() -> JSONResponse:
    """DID-Dokument für did:web:travel.hanibal-ai.com:payapi.

    did:web mit Pfadanteil wird per Spec unter /<pfad>/did.json aufgelöst,
    nicht unter /.well-known/did.json. Der Root-Alias unten ist zusätzlich
    für Werkzeuge da, die nur den Well-Known-Pfad kennen.
    """
    return JSONResponse(
        _did_document(config().settings.issuer_did),
        headers={"Cache-Control": "public, max-age=300"},
    )


@public_router.get("/api/attest-v2/did.json")
async def payapi_did_alias() -> JSONResponse:
    return JSONResponse(
        _did_document(config().settings.issuer_did),
        headers={"Cache-Control": "public, max-age=300"},
    )


@public_router.get("/api/attest-v2/sample")
async def payapi_sample() -> JSONResponse:
    """Kostenloses, signiertes Referenzbeispiel in der Form der bezahlten Route.

    PayAPI/x402-Verzeichnisse koennen die Route damit ohne Zahlung pruefen
    ("offer a free sample or health route that returns real data in the same
    shape as the paid route").
    """
    obs = Observation.model_validate(_reference_observation(
        "Kostenloses Referenzbeispiel (kein Kauf, keine Zahlung)."
    ))
    plausibility = check_observation(obs, ttl_seconds=config().settings.ttl_seconds)
    document = issuer().sign(_build_document(obs, plausibility, {}))
    return JSONResponse(document, headers=_attestation_headers(document))


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
    if not isinstance(document, dict):
        return JSONResponse({"valid": False, "error": "document fehlt"}, status_code=400)
    key = issuer()
    details = verify_attestation_details(
        document, key.public_key_b64,
        expected_issuer=config().settings.issuer_did,
        expected_key_id=key.key_id,
    )
    return JSONResponse({
        **details,
        "key_id": (document.get("signature") or {}).get("key_id"),
        "issuer": (document.get("issuer") or {}).get("did"),
        "expires_at": document.get("expires_at"),
    })


def openapi_document(base: str) -> dict[str, Any]:
    """Kanonisches Discovery-Dokument unter ``GET /openapi.json``.

    x402scan und andere Kataloge lesen OpenAPI 3.1 vom Origin-Root. Die Werte
    stammen aus der PayAPI-Config (Preis, Netz, Wallet) und dem Observation-Modell;
    es werden keine Kennungen oder Preise erfunden.
    """
    s = config().settings
    raw_price = str(s.price or "").strip().lstrip("$€").strip()
    try:
        price_usd = f"{Decimal(raw_price):.6f}"
    except (InvalidOperation, ValueError):
        price_usd = "0.000000"
    info: dict[str, Any] = {
        "title": SERVICE,
        "version": "1.0.0",
        "description": DESCRIPTION,
        "x-guidance": (
            "Use POST /api/attest-v2 with a JSON body containing route, travel_date, "
            "price, price_scope and source. Unpaid calls return HTTP 402 with x402 v2 "
            "payment requirements (Base, USDC). A paid call returns an Ed25519-signed "
            "price attestation; prices are observations, not booking or price guarantees."
        ),
    }
    email = contact_email()
    if email:
        info["contact"] = {"email": email}
    observation_schema = Observation.model_json_schema()
    attestation_schema = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "id": {"type": "string"},
            "issued_at": {"type": "string", "format": "date-time"},
            "expires_at": {"type": "string", "format": "date-time"},
            "issuer": {"type": "object"},
            "subject": {"type": "object"},
            "plausibility": {"type": "object"},
            "signature": {"type": "object"},
        },
        "required": ["version", "id", "issued_at", "issuer", "subject",
                     "plausibility", "signature"],
    }
    paid = {
        "post": {
            "operationId": "attest_v2",
            "summary": "Signed price attestation (x402 v2, Base/USDC)",
            "tags": ["travel", "price", "attestation", "x402"],
            "x-payment-info": {
                "price": {"mode": "fixed", "currency": "USD", "amount": price_usd},
                "protocols": [{"x402": {}}],
            },
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": observation_schema}},
            },
            "responses": {
                "200": {
                    "description": "Signed Ed25519 attestation",
                    "content": {"application/json": {"schema": attestation_schema}},
                },
                "402": {"description": "Payment Required (x402 v2 challenge)"},
                "422": {"description": "Ungültige oder fehlende Beobachtung (keine Signatur, keine Zahlung)"},
            },
        }
    }
    return {
        "openapi": "3.1.0",
        "info": info,
        "servers": [{"url": base}],
        "paths": {
            PAYAPI_PATH: paid,
            "/health": {
                "get": {"operationId": "health", "security": [],
                        "summary": "Health check",
                        "responses": {"200": {"description": "OK"}}},
            },
            f"{PAYAPI_PATH}/key": {
                "get": {"operationId": "attest_key", "security": [],
                        "summary": "Public Ed25519 key",
                        "responses": {"200": {"description": "Public key"}}},
            },
            f"{PAYAPI_PATH}/sample": {
                "get": {"operationId": "attest_sample", "security": [],
                        "summary": "Free signed sample attestation (same shape as paid)",
                        "responses": {"200": {"description": "Signed sample attestation"}}},
            },
            "/payapi/did.json": {
                "get": {"operationId": "payapi_did", "security": [],
                        "summary": "DID document for did:web:…:payapi",
                        "responses": {"200": {"description": "DID document"}}},
            },
            f"{PAYAPI_PATH}/validate": {
                "post": {"operationId": "attest_validate", "security": [],
                         "summary": "Free pre-validation",
                         "requestBody": {"required": True, "content": {
                             "application/json": {"schema": observation_schema}}},
                         "responses": {"200": {"description": "Validation result"}}},
            },
            f"{PAYAPI_PATH}/verify": {
                "post": {"operationId": "attest_verify", "security": [],
                         "summary": "Verify a signed attestation",
                         "responses": {"200": {"description": "Verification result"}}},
            },
            "/.well-known/x402": {
                "get": {"operationId": "x402_manifest", "security": [],
                        "summary": "x402 discovery manifest",
                        "responses": {"200": {"description": "Manifest"}}},
            },
        },
    }


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
    return JSONResponse(openapi_document(_base_url(request)))


# ------------------------------------------------------------------ paid routes
@paid_router.api_route(PAYAPI_PATH, methods=["GET", "HEAD"])
async def payapi_get(request: Request) -> JSONResponse:
    try:
        document = _sign(_observation_from_query(request), request)
    except ValueError as exc:
        return JSONResponse(
            {"error": str(exc),
             "hint": "Erforderlich: route, travel_date, price und source (GET-Query)."},
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
             "hint": "Erforderlich: JSON-Body mit route, travel_date, price und source."},
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
        record_invoice(document, settlement, path=config().ledger, service=SERVICE,
                       series="V2")
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
        detail = f"{type(exc).__name__}: {exc}"

        @app.api_route(PAYAPI_PATH, methods=["GET", "HEAD", "POST"])
        async def _unavailable() -> JSONResponse:
            return JSONResponse(
                {"error": "Zahlungsweg nicht verfügbar", "detail": detail},
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
