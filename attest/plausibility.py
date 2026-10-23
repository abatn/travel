"""Plausibilitätsprüfung vor der Signatur.

Eine Attestierung ist nur so viel wert wie ihre Prüfung. Die Regeln sind
bewusst konservativ und werden im Dokument einzeln ausgewiesen, damit ein
anderer Agent sie nachvollziehen kann.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from .models import Observation

MAX_PER_PERSON = Decimal("20000")
MAX_TOTAL = Decimal("100000")
MIN_PRICE = Decimal("1")


def _check(check_id: str, status: str, detail: str) -> dict[str, str]:
    return {"id": check_id, "status": status, "detail": detail}


def check_observation(obs: Observation, *, ttl_seconds: int,
                      now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    observed = obs.observed_at or now
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    checks: list[dict[str, str]] = []

    # 1) Strecke
    origin, destination = obs.route.split("-")
    checks.append(
        _check("route_distinct", "pass", "Start und Ziel unterscheiden sich")
        if origin != destination
        else _check("route_distinct", "reject", "Start und Ziel sind identisch")
    )

    # 2) Preisrahmen je Preisbasis
    limit = MAX_PER_PERSON if obs.price_scope in ("per_person", "per_night") else MAX_TOTAL
    if obs.price > limit:
        checks.append(_check("price_range", "reject",
                             f"{obs.price} {obs.currency} über Grenze {limit}"))
    elif obs.price < MIN_PRICE:
        checks.append(_check("price_range", "warn",
                             f"{obs.price} {obs.currency} ist ungewöhnlich niedrig"))
    else:
        checks.append(_check("price_range", "pass", f"innerhalb {limit} {obs.currency}"))

    # 3) Reisedatum
    today = now.date()
    if obs.travel_date < today - timedelta(days=1):
        checks.append(_check("travel_date", "reject", "Reisedatum liegt in der Vergangenheit"))
    elif obs.travel_date > today + timedelta(days=400):
        checks.append(_check("travel_date", "reject", "Reisedatum liegt über 400 Tage entfernt"))
    else:
        checks.append(_check("travel_date", "pass", "Reisedatum im zulässigen Fenster"))

    # 4) Beobachtungszeitpunkt / Frische
    age = now - observed
    if age < timedelta(minutes=-5):
        checks.append(_check("freshness", "reject", "observed_at liegt in der Zukunft"))
    elif age > timedelta(seconds=ttl_seconds * 2):
        checks.append(_check("freshness", "reject",
                             f"Beobachtung ist {int(age.total_seconds())}s alt (TTL {ttl_seconds}s)"))
    elif age > timedelta(seconds=ttl_seconds):
        checks.append(_check("freshness", "warn",
                             f"Beobachtung ist älter als TTL ({int(age.total_seconds())}s)"))
    else:
        checks.append(_check("freshness", "pass", f"Alter {int(age.total_seconds())}s"))

    # 5) Quellenangabe
    if obs.source_url:
        checks.append(_check("provenance", "pass", "Quell-URL vorhanden"))
    else:
        checks.append(_check("provenance", "warn", "keine Quell-URL angegeben"))

    # 6) Preisbasis
    if obs.price_scope == "per_stay" and obs.passengers > 9:
        checks.append(_check("price_scope", "warn", "per_stay mit vielen Personen"))
    else:
        checks.append(_check("price_scope", "pass", obs.price_scope))

    statuses = {c["status"] for c in checks}
    overall = "reject" if "reject" in statuses else ("warn" if "warn" in statuses else "ok")
    return {
        "status": overall,
        "checks": checks,
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "ttl_seconds": ttl_seconds,
    }
