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

SAMPLE_OUTPUT: dict[str, Any] = {
    "version": "1",
    "id": "att_…",
    "issued_at": "2026-10-23T18:05:23Z",
    "subject": {"route": "BER-FCO", "price": "129.99", "currency": "EUR"},
    "plausibility": {"status": "ok"},
    "signature": {"alg": "Ed25519", "key_id": "…", "value": "…"},
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


def bazaar_extension() -> dict[str, Any]:
    """Bazaar-Discovery-Erweiterung (x402 v2), wie sie Indexer lesen."""
    return {
        "info": {
            "input": {
                "type": "http",
                "method": "POST",
                "bodyType": "json",
                "body": SAMPLE_INPUT,
            },
            "output": {
                "type": "json",
                "example": SAMPLE_OUTPUT,
            },
        },
        "schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "input": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "http"},
                        "method": {"type": "string", "enum": ["POST", "PUT", "PATCH"]},
                        "bodyType": {"type": "string", "enum": ["json"]},
                        "body": {
                            "type": "object",
                            "properties": {
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
                            },
                            "required": ["route", "travel_date", "price", "price_scope", "source"],
                        },
                    },
                    "required": ["type", "method", "bodyType", "body"],
                },
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

