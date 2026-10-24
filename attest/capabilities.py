"""Capability-Mikromarkt (M3): maschinenlesbarer Katalog der Fähigkeiten.

Der Katalog beschreibt, was der Reise-Agent anbietet und was davon bereits
bezahlbar ist. `status: available` bedeutet: Der Endpunkt existiert und wird
über x402 (HTTP 402) abgerechnet. `status: planned` bedeutet ausdrücklich:
noch nicht als bezahlter Endpunkt verfügbar – es fließt kein Geld.

Der Katalog enthält keine Secrets und keine erfundenen IDs. Preise werden aus
der Konfiguration gelesen (`payment.price`), damit Anzeige und x402-Gate
nicht auseinanderlaufen.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

from .config import Settings
from .discovery import SAMPLE_INPUT, atomic_amount, contact_email
from .x402_gate import ATTEST_PATH

#: Fallback-Preis je Attestierung, wenn die Konfiguration keinen gültigen Wert liefert.
DEFAULT_ATTEST_PRICE = "0.01"

#: Währungssymbole/-präfixe, die in `payment.price` erlaubt sind (z. B. "$0.01").
_PRICE_PREFIXES = ("USDC", "USD", "EUR", "€", "$")

#: Fähigkeiten des Agenten. `price_usdc` ist ein Dezimal-String in USDC.
#: Bei `attest_price` ist der Wert hier nur der Fallback; `capabilities_document`
#: ersetzt ihn durch den konfigurierten Preis.
CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "attest_price",
        "name": "Preis-Attestierung",
        "description": (
            "Signierte Preis-Attestierung (Ed25519) für eine beobachtete "
            "Flugpreis-Angabe inklusive Quelle und Zeitstempel."
        ),
        "price_usdc": "0.01",
        "status": "available",
        "endpoint": ATTEST_PATH,
        "method": "POST",
        "input_schema": {
            "type": "object",
            "properties": {
                "route": {
                    "type": "string",
                    "pattern": "^[A-Za-z]{3}-[A-Za-z]{3}$",
                    "description": "Strecke als IATA-Paar, z. B. BER-FCO",
                },
                "travel_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Reisedatum (YYYY-MM-DD)",
                },
                "price": {
                    "type": "string",
                    "description": "Beobachteter Preis, z. B. \"129.99\"",
                },
                "currency": {
                    "type": "string",
                    "enum": ["EUR", "USD", "GBP", "CHF", "SEK", "NOK", "DKK", "PLN"],
                    "default": "EUR",
                },
                "price_scope": {
                    "type": "string",
                    "enum": ["per_person", "per_night", "total", "per_stay"],
                },
                "source": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 64,
                    "description": "Quellen-ID, z. B. googleflights-local",
                },
                "source_url": {
                    "type": "string",
                    "format": "uri",
                    "maxLength": 500,
                },
                "passengers": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 9,
                    "default": 1,
                },
            },
            "required": ["route", "travel_date", "price", "price_scope", "source"],
        },
        "example": SAMPLE_INPUT,
        "note": "Preis wird aus der Konfiguration gelesen (payment.price).",
    },
    {
        "id": "search_flights",
        "name": "Flugsuche",
        "description": "Flugsuche über mehrere Quellen; geplant, noch nicht verfügbar.",
        "price_usdc": "0.02",
        "status": "planned",
        "endpoint": "/api/search",
        "method": "POST",
        # Geplant: Eingabeschema ist noch nicht festgelegt, daher bewusst leer.
        "input_schema": {"type": "object", "description": "Noch nicht festgelegt."},
        "example": {},
        "note": "Geplant – Endpunkt nimmt noch keine Zahlungen an.",
    },
    {
        "id": "resolve_place",
        "name": "Ortsauflösung",
        "description": "Ortsauflösung für Städte und Flughäfen; geplant, noch nicht verfügbar.",
        "price_usdc": "0.005",
        "status": "planned",
        "endpoint": "/api/place",
        "method": "GET",
        "input_schema": {"type": "object", "description": "Noch nicht festgelegt."},
        "example": {},
        "note": "Geplant – Endpunkt nimmt noch keine Zahlungen an.",
    },
    {
        "id": "price_history",
        "name": "Preisverlauf",
        "description": "Preisverlauf einer Strecke; geplant, noch nicht verfügbar.",
        "price_usdc": "0.01",
        "status": "planned",
        "endpoint": "/api/history",
        "method": "GET",
        "input_schema": {"type": "object", "description": "Noch nicht festgelegt."},
        "example": {},
        "note": "Geplant – Endpunkt nimmt noch keine Zahlungen an.",
    },
]


def normalize_price(price: str | None, fallback: str = DEFAULT_ATTEST_PRICE) -> str:
    """Normalisiert `payment.price` (z. B. "$0.01") zu einem Dezimal-String.

    Ungültige, fehlende oder nicht-positive Werte ergeben `fallback`.
    """
    raw = str(price or "").strip()
    for prefix in _PRICE_PREFIXES:
        if raw.upper().startswith(prefix):
            raw = raw[len(prefix):].strip()
            break
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return fallback
    if not value.is_finite() or value <= 0:
        return fallback
    return format(value.normalize(), "f")


def _base_url(settings: Settings, base_url: str | None) -> str:
    """Explizite Basis-URL vor `public_base_url` aus der Konfiguration."""
    return (base_url or settings.public_base_url or "").rstrip("/")


def capabilities_document(settings: Settings, base_url: str | None = None) -> dict[str, Any]:
    """Baut das Katalog-Dokument (Version 1) für Discovery und Agenten.

    `base_url` überschreibt `settings.public_base_url`. Ist beides leer,
    bleiben die `url`-Felder relativ zum ausliefernden Host.
    """
    base = _base_url(settings, base_url)
    attest_price = normalize_price(settings.price)
    capabilities: list[dict[str, Any]] = []

    for capability in CAPABILITIES:
        entry = deepcopy(capability)
        if entry["id"] == "attest_price":
            entry["price_usdc"] = attest_price
        entry["price_atomic"] = int(atomic_amount(entry["price_usdc"]))
        entry["url"] = f"{base}{entry['endpoint']}"
        capabilities.append(entry)

    return {
        "version": "1",
        "provider": {
            "name": "Reise-Agent",
            "url": base,
            "description": (
                "Agent für Flugpreis-Recherche und signierte Preis-Attestierungen."
            ),
        },
        "contact": contact_email(),
        "payment": {
            "protocol": "x402",
            "network": settings.network,
            "asset": settings.asset,
            "pay_to": settings.pay_to,
            "currency": "USDC",
        },
        "capabilities": capabilities,
    }
