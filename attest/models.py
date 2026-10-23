"""Ein- und Ausgabemodelle für /api/attest."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

PriceScope = Literal["per_person", "per_night", "total", "per_stay"]
Currency = Literal["EUR", "USD", "GBP", "CHF", "SEK", "NOK", "DKK", "PLN"]


class Observation(BaseModel):
    """Eine Preisbeobachtung, die attestiert werden soll."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    route: str = Field(..., description="Strecke als IATA-Paar, z. B. BER-FCO")
    travel_date: date = Field(..., description="Reisedatum (YYYY-MM-DD)")
    price: Decimal = Field(..., gt=0, le=100_000, description="Beobachteter Preis")
    currency: Currency = "EUR"
    price_scope: PriceScope = Field(
        ..., description="per_person | per_night | total | per_stay"
    )
    source: str = Field(..., min_length=1, max_length=64,
                        description="Quellen-ID, z. B. googleflights-local")
    source_url: str | None = Field(None, max_length=500)
    observed_at: datetime | None = Field(
        None, description="Zeitpunkt der Beobachtung (Default: jetzt)"
    )
    passengers: int = Field(1, ge=1, le=9)
    cabin: str | None = Field(None, max_length=24)
    note: str | None = Field(None, max_length=500)

    @field_validator("route")
    @classmethod
    def _normalize_route(cls, value: str) -> str:
        value = value.upper().strip()
        parts = value.split("-")
        if len(parts) != 2 or any(len(p) != 3 or not p.isalpha() for p in parts):
            raise ValueError("route muss ein IATA-Paar wie BER-FCO sein")
        return value

    @field_validator("source")
    @classmethod
    def _normalize_source(cls, value: str) -> str:
        value = value.strip().lower()
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
        if not value or value[0] not in "abcdefghijklmnopqrstuvwxyz0123456789":
            raise ValueError("source muss mit Buchstabe/Zahl beginnen")
        if any(ch not in allowed for ch in value):
            raise ValueError("source darf nur a-z, 0-9, '.', '_', '-' enthalten")
        return value

    @field_validator("source_url")
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("source_url muss eine absolute http(s)-URL sein")
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def _upper_currency(cls, value: str) -> str:
        return str(value).upper()
