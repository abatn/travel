"""Betreiberangaben: Laden, Pflichtfeldprüfung, Indexierbarkeit.

Die Seiten /impressum und /datenschutz sind nur dann indexierbar, wenn alle
Pflichtfelder echte Werte enthalten. Platzhalter in eckigen Klammern
(`[Name]`, `[deine@mail.de]`) gelten bewusst als "nicht ausgefüllt".
Erfundene Angaben werden nie erzeugt.
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

OPTIONAL_IMPRESSUM: dict[str, str] = {
    "telefon": "Telefon",
    "registergericht": "Registergericht",
    "registernummer": "Registernummer",
}
OPTIONAL_DATENSCHUTZ: dict[str, str] = {
    "email_hosting": "E-Mail-Hosting",
    "auftragsverarbeiter": "Auftragsverarbeiter",
}


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


def is_placeholder(value: str) -> bool:
    """True für typische Platzhalter, die noch ersetzt werden müssen."""
    value = str(value or "").strip()
    if not value:
        return False
    if (value.startswith("[") and value.endswith("]")) or (
        value.startswith("<") and value.endswith(">")
    ):
        return True
    return value.upper() in {"TODO", "TBD", "CHANGEME", "PLATZHALTER"}


def missing(data: dict[str, Any], kind: str) -> list[str]:
    """Liefert die Labels der fehlenden Pflichtfelder (leer oder Platzhalter)."""
    fields = IMPRESSUM_REQUIRED if kind == "impressum" else DATENSCHUTZ_REQUIRED
    optional = OPTIONAL_IMPRESSUM if kind == "impressum" else OPTIONAL_DATENSCHUTZ
    section = "betreiber" if kind == "impressum" else "datenschutz"

    def not_filled(key: str) -> bool:
        value = _value(data, section, key)
        return (not value) or is_placeholder(value)

    missing_required = [label for key, label in fields.items() if not_filled(key)]
    # Optionale Felder dürfen leer sein – aber ein Platzhalter muss ersetzt
    # oder das Feld geleert werden, sonst bleibt die Seite noindex.
    placeholder_optional = [
        f"{label} (Platzhalter)" for key, label in optional.items()
        if is_placeholder(_value(data, section, key))
    ]
    return missing_required + placeholder_optional


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
