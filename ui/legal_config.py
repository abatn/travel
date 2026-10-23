"""Betreiberangaben: Laden, Pflichtfeldprüfung, Indexierbarkeit.

Die Seiten /impressum und /datenschutz sind nur dann indexierbar, wenn alle
Pflichtfelder echte Werte enthalten. Erfundene Angaben werden nie erzeugt.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_PATH = HERE / "legal.yaml"

# Pflichtfelder. USt-IdNr. darf "keine" sein (z. B. Kleinunternehmer).
IMPRESSUM_REQUIRED: dict[str, str] = {
    "name": "Name / Firma",
    "strasse": "Straße und Hausnummer",
    "plz_ort": "PLZ und Ort",
    "land": "Land",
    "email": "E-Mail-Adresse",
    "umsatzsteuer_id": "USt-IdNr. (oder \"keine\")",
    "verantwortlich": "Verantwortliche Person (§ 18 Abs. 2 MStV)",
}

DATENSCHUTZ_REQUIRED: dict[str, str] = {
    "hosting": "Hosting-Anbieter",
    "kontakt_datenschutz": "Datenschutz-Kontakt",
    "aufbewahrung_logs": "Aufbewahrung der Server-Logs",
    "aufsichtsbehoerde": "Zuständige Datenschutz-Aufsichtsbehörde",
    "stand": "Stand der Datenschutzerklärung",
}

OPTIONAL_IMPRESSUM = ("telefon", "registergericht", "registernummer")
OPTIONAL_DATENSCHUTZ = ("email_hosting", "auftragsverarbeiter")


def config_path(path: str | Path | None = None) -> Path:
    """Pfad zur Legal-Konfiguration (Tests können LEGAL_CONFIG setzen)."""
    if path:
        return Path(path)
    override = os.environ.get("LEGAL_CONFIG", "").strip()
    return Path(override) if override else DEFAULT_PATH


def load(path: str | Path | None = None) -> dict[str, Any]:
    target = config_path(path)
    try:
        with target.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _value(data: dict[str, Any], section: str, key: str) -> str:
    block = data.get(section) or {}
    if not isinstance(block, dict):
        return ""
    return str(block.get(key) or "").strip()


def missing(data: dict[str, Any], kind: str) -> list[str]:
    """Liefert die Labels der fehlenden Pflichtfelder."""
    fields = IMPRESSUM_REQUIRED if kind == "impressum" else DATENSCHUTZ_REQUIRED
    section = "betreiber" if kind == "impressum" else "datenschutz"
    return [label for key, label in fields.items() if not _value(data, section, key)]


def is_complete(data: dict[str, Any], kind: str) -> bool:
    return not missing(data, kind)


def status(data: dict[str, Any]) -> dict[str, Any]:
    """Kompakte Übersicht für Startseite/Logs/Tests."""
    return {
        "impressum": {
            "indexable": is_complete(data, "impressum"),
            "missing": missing(data, "impressum"),
        },
        "datenschutz": {
            "indexable": is_complete(data, "datenschutz"),
            "missing": missing(data, "datenschutz"),
        },
    }
