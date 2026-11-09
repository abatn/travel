"""Discovery-Daten für x402-Bazaar, llms.txt und Registrierung."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent

SAMPLE_INPUT: dict[str, Any] = {
    "route": "BER-FCO",
    "travel_date": "2026-11-05",
    "price": "129.99",
    "currency": "EUR",
    "price_scope": "per_person",
    "source": "googleflights-local",
    "source_url": "https://www.google.com/travel/flights",
    "passengers": 1,
}

from datetime import date, timedelta

# Beispiel-Reisedatum dynamisch beim Start: ein fest eingetragenes Datum wird
# innerhalb weniger Tage unglaubwuerdig (Plausibilitaet: nicht in der
# Vergangenheit, maximal 400 Tage voraus) und laesst dann jeden Health-Check
# der Indexer scheitern. +30 Tage bleibt bis zum naechsten Deploy/Neustart gueltig.
_SAMPLE_TRAVEL_DATE = (date.today() + timedelta(days=30)).isoformat()

SAMPLE_INPUT: dict[str, Any] = {
    "route": "BER-FCO",
    "travel_date": _SAMPLE_TRAVEL_DATE,
    "price": "129.99",
    "currency": "EUR",
    "price_scope": "per_person",
    "source": "googleflights-local",
    "source_url": "https://www.google.com/travel/flights",
    "passengers": 1,
}

QUERY_SAMPLE_INPUT: dict[str, Any] = {
    "route": "BER-FCO",
    "travel_date": _SAMPLE_TRAVEL_DATE,
    "price": "129.99",
    "currency": "EUR",
    "price_scope": "per_person",
    "source": "googleflights-local",
    "source_url": "https://www.google.com/travel/flights",
    "passengers": 1,
}

# Vollstaendiges Beispiel in der Form des echten Dokuments (keine
# Platzhalter-Ellipsis): Agenten und Indexer sollen die Antwort vor dem Kauf
# pruefen koennen. Kennungen sind bewusst neutral (die echten Werte stehen im
# jeweiligen /key- bzw. /verify-Endpunkt).
SAMPLE_OUTPUT: dict[str, Any] = {
    "version": "1",
    "service": "Reise-Agent Attest",
    "instance": "example",
    "id": "att_0123456789abcdef0123456789abcdef",
    "issued_at": "2026-01-01T12:00:00Z",
    "expires_at": "2026-01-01T12:05:00Z",
    "issuer": {
        "did": "did:web:example.org",
        "key_id": "key-id-example",
        "public_key": "base64url-public-key",
        "alg": "Ed25519",
        "pay_to": "0x1111111111111111111111111111111111111111",
    },
    "subject": {
        "route": "BER-FCO",
        "travel_date": _SAMPLE_TRAVEL_DATE,
        "price": "129.99",
        "currency": "EUR",
        "price_scope": "per_person",
        "passengers": 1,
        "cabin": None,
        "source": "googleflights-local",
        "source_url": "https://www.google.com/travel/flights",
        "observed_at": "2026-01-01T12:00:00Z",
        "note": None,
    },
    "plausibility": {"status": "ok", "checks": [], "ttl_seconds": 300},
    "payment": {"payer": "0x2222222222222222222222222222222222222222",
                "network": "eip155:8453", "scheme": "exact",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "amount": "10000", "x402_version": 2},
    "terms": {"meaning": "Beobachtung, keine Buchungsgarantie und keine Preisgarantie.",
              "verification": "/api/attest/verify"},
    "signature": {"alg": "Ed25519", "key_id": "key-id-example",
                  "value": "base64url-signature"},
}


def atomic_amount(price: str, decimals: int = 6) -> str:
    raw = str(price).strip().lstrip("$€").strip()
    try:
        value = Decimal(raw) * (Decimal(10) ** decimals)
        return str(int(value))
    except (InvalidOperation, ValueError):
        return "0"


def contact_email() -> str:
    """Liest die Kontakt-E-Mail aus ui/legal.yaml (leer, wenn nicht konfiguriert)."""
    try:
        data = yaml.safe_load((ROOT / "ui" / "legal.yaml").read_text(encoding="utf-8")) or {}
        return str(((data.get("betreiber") or {}).get("email")) or "").strip()
    except Exception:
        return ""


def bazaar_extension(method: str = "POST") -> dict[str, Any]:
    """Bazaar-Discovery-Erweiterung (x402 v2) — methodenspezifisch.

    Query-Methoden (GET/HEAD/DELETE) deklarieren ``queryParams``, Body-Methoden
    (POST/PUT/PATCH) einen JSON-``body``. Die deklarierte Methode muss zur
    tatsaechlich geprobten Route passen, sonst scheitert die Facilitator-
    Vorpruefung ``bazaar.info.input.method.matches_request`` (CDP /validate).
    """
    m = (method or "POST").upper()
    fields: dict[str, Any] = {
        "route": {"type": "string", "pattern": "^[A-Za-z]{3}-[A-Za-z]{3}$"},
        "travel_date": {"type": "string", "format": "date"},
        "price": {"type": "string"},
        "currency": {"type": "string"},
        "price_scope": {
            "type": "string",
            "enum": ["per_person", "per_night", "total", "per_stay"],
        },
        "source": {"type": "string"},
        "source_url": {"type": "string", "format": "uri"},
        "observed_at": {"type": "string", "format": "date-time"},
        "passengers": {"type": "integer", "minimum": 1, "maximum": 9},
        "cabin": {"type": "string"},
        "note": {"type": "string"},
    }
    required = ["route", "travel_date", "price", "price_scope", "source"]

    if m in ("GET", "HEAD", "DELETE"):
        info_input: dict[str, Any] = {
            "type": "http",
            "method": m,
            "queryParams": QUERY_SAMPLE_INPUT,
        }
        input_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "const": "http"},
                "method": {"type": "string", "enum": ["GET", "HEAD", "DELETE"]},
                "queryParams": {
                    "type": "object",
                    "properties": fields,
                    "required": required,
                    "additionalProperties": False,
                },
            },
            "required": ["type", "method", "queryParams"],
        }
    else:
        info_input = {
            "type": "http",
            "method": m,
            "bodyType": "json",
            "body": SAMPLE_INPUT,
        }
        input_schema = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "const": "http"},
                "method": {"type": "string", "enum": ["POST", "PUT", "PATCH"]},
                "bodyType": {"type": "string", "enum": ["json"]},
                "body": {
                    "type": "object",
                    "properties": fields,
                    "required": required,
                    "additionalProperties": False,
                },
            },
            "required": ["type", "method", "bodyType", "body"],
        }

    return {
        "info": {
            "input": info_input,
            "output": {"type": "json", "example": SAMPLE_OUTPUT},
        },
        "schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "input": input_schema,
                "output": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "example": {"type": "object"},
                    },
                    "required": ["type"],
                },
            },
            "required": ["input"],
        },
    }

OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version", "id", "issued_at", "expires_at", "issuer", "subject",
                 "plausibility", "signature"],
    "properties": {
        "version": {"type": "string"},
        "id": {"type": "string", "description": "Attestation-ID (att_…)"},
        "issued_at": {"type": "string", "format": "date-time"},
        "expires_at": {"type": "string", "format": "date-time"},
        "issuer": {
            "type": "object",
            "properties": {
                "did": {"type": "string"},
                "key_id": {"type": "string"},
                "public_key": {"type": "string"},
                "alg": {"type": "string", "const": "Ed25519"},
                "pay_to": {"type": "string"},
            },
        },
        "subject": {
            "type": "object",
            "properties": {
                "route": {"type": "string", "pattern": "^[A-Z]{3}-[A-Z]{3}$"},
                "travel_date": {"type": "string", "format": "date"},
                "price": {"type": "string"},
                "currency": {"type": "string"},
                "price_scope": {"type": "string"},
                "passengers": {"type": "integer"},
                "cabin": {"type": ["string", "null"]},
                "source": {"type": "string"},
                "source_url": {"type": ["string", "null"], "format": "uri"},
                "observed_at": {"type": "string", "format": "date-time"},
                "note": {"type": ["string", "null"]},
            },
        },
        "plausibility": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "checks": {"type": "array", "items": {"type": "string"}},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        },
        "payment": {"type": "object"},
        "terms": {"type": "object"},
        "signature": {
            "type": "object",
            "required": ["alg", "key_id", "value"],
            "properties": {
                "alg": {"type": "string", "const": "Ed25519"},
                "key_id": {"type": "string"},
                "value": {"type": "string"},
            },
        },
    },
}

