"""Quellenrechte: Filter für Anzeige und Verkauf.

Regel (siehe docs/QUELLENRECHTE.md): Fremde Preise dürfen nur angezeigt werden,
wenn der Datenanbieter die kommerzielle Anzeige erlaubt. Fehlt ein Beleg, gilt
Default-Deny. Die Lizenz eines MCP-Wrappers (z. B. MIT) ist **kein** Nachweis
für Datenrechte.

Statuswerte je Quelle in ``registry.yaml`` unter ``rights.status``:
  own         - eigener Code, keine fremden Daten
  approved    - schriftliche/commercial Erlaubnis dokumentiert
  unverified  - keine Erlaubnis gefunden (Default)
  prohibited  - Anzeige/Verkauf ausdrücklich nicht erlaubt

Steuerung über Umgebungsvariablen:
  RIGHTS_ENFORCE=0           Filter komplett aus (nur lokale Forschung)
  RIGHTS_INCLUDE_UNVERIFIED=0  auch unverified ausschließen (maximal strikt)
"""
from __future__ import annotations

import os
from typing import Any, Iterable

VALID = ("own", "approved", "unverified", "prohibited")


def status_of(provider: dict[str, Any]) -> str:
    """Status einer Quelle; fehlende Angabe zählt als ``unverified``."""
    rights = provider.get("rights") or {}
    status = str(rights.get("status") or "unverified").strip().lower()
    return status if status in VALID else "unverified"


def display_allowed(provider: dict[str, Any], *, enforce: bool = True,
                    include_unverified: bool = True) -> bool:
    """Darf diese Quelle in Suchergebnissen angezeigt/verkauft werden?"""
    if not enforce:
        return True
    status = status_of(provider)
    if status in ("own", "approved"):
        return True
    if status == "prohibited":
        return False
    return include_unverified


def enforce_enabled() -> bool:
    return os.getenv("RIGHTS_ENFORCE", "1").strip() not in ("0", "false", "no", "off")


def include_unverified() -> bool:
    return os.getenv("RIGHTS_INCLUDE_UNVERIFIED", "1").strip() not in ("0", "false", "no", "off")


def filter_providers(providers: Iterable[dict[str, Any]], *,
                     enforce: bool | None = None,
                     include_unver: bool | None = None) -> list[dict[str, Any]]:
    """Entfernt Quellen, die nicht angezeigt werden dürfen."""
    enf = enforce_enabled() if enforce is None else enforce
    inc = include_unverified() if include_unver is None else include_unver
    return [p for p in providers if display_allowed(p, enforce=enf, include_unverified=inc)]


def blocked_providers(providers: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    """Liste der gesperrten Quellen für Statusanzeige/Logs."""
    out = []
    for p in providers:
        if not display_allowed(p, enforce=True, include_unverified=include_unverified()):
            rights = p.get("rights") or {}
            out.append({
                "id": str(p.get("id")),
                "category": str(p.get("category")),
                "status": status_of(p),
                "reason": str(rights.get("evidence") or ""),
            })
    return out
