"""Mehrsprachigkeit: JSON-Locales, Auflösung per Query/Cookie/Header.

Kein Build-Schritt, keine Zusatzbibliothek. Die Quelle ist Deutsch (`de.json`);
fehlt ein Schlüssel in einer Sprache, wird Deutsch verwendet, danach der
Schlüssel selbst. Begründung und Alternativen: `i18n/ENTSCHEIDUNG.md`.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED: tuple[str, ...] = ("de", "en", "fr", "es", "ar")
DEFAULT = "de"
RTL = {"ar"}
COOKIE = "lang"
LOCALES = Path(__file__).resolve().parent.parent / "ui" / "locales"


@lru_cache(maxsize=None)
def load(lang: str) -> dict[str, str]:
    """Lädt eine Locale (Basis + optionale Zusatzdateien (unter ui/locales)), Fallback Deutsch.

    Zusatzdateien erlauben paralleles Arbeiten ohne Konflikte:
    ``<code>.json`` (Basis), ``<code>.pages.json``, ``<code>.legal.json``.
    """
    code = lang if lang in SUPPORTED else DEFAULT
    merged: dict[str, str] = {}
    # Alle Dateien der Sprache, z. B. de.json, de.legal.json, de.results.json.
    # Reihenfolge: Basis zuerst, Zusatzdateien danach (überschreiben).
    base = LOCALES / f"{code}.json"
    files = [base] if base.is_file() else []
    files += sorted(LOCALES.glob(f"{code}.*.json"))
    for path in files:
        try:
            merged.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return merged


@lru_cache(maxsize=None)
def _bundle() -> dict[str, dict[str, str]]:
    return {code: load(code) for code in SUPPORTED}


def t(lang: str, key: str, default: str | None = None, **params: Any) -> str:
    """Übersetzt einen Schlüssel; Fallback: Zielsprache → Deutsch → default → Schlüssel."""
    code = lang if lang in SUPPORTED else DEFAULT
    text = _bundle().get(code, {}).get(key)
    if text is None:
        text = _bundle()[DEFAULT].get(key)
    if text is None:
        text = default if default is not None else key
    if params:
        try:
            return text.format(**params)
        except (KeyError, IndexError):
            return text
    return text


def translator(lang: str):
    """Gibt eine Funktion ``t(key, **params)`` für Templates/Code zurück."""
    return lambda key, **params: t(lang, key, **params)


def is_rtl(lang: str) -> bool:
    return lang in RTL


def direction(lang: str) -> str:
    return "rtl" if is_rtl(lang) else "ltr"


def _from_accept_header(value: str | None) -> str | None:
    """Einfache Auswertung von ``Accept-Language`` (erste unterstützte Sprache)."""
    if not value:
        return None
    for part in value.split(","):
        code = part.split(";")[0].strip().lower().replace("_", "-")
        base = code.split("-")[0]
        if base in SUPPORTED:
            return base
    return None


def resolve(request) -> str:
    """Sprache bestimmen: ?lang= → Cookie → Accept-Language → Deutsch."""
    wanted = (request.query_params.get("lang") or "").strip().lower()
    if wanted in SUPPORTED:
        return wanted
    cookie = (request.cookies.get(COOKIE) or "").strip().lower()
    if cookie in SUPPORTED:
        return cookie
    return _from_accept_header(request.headers.get("accept-language")) or DEFAULT


def swatch_update_needed(request, lang: str) -> bool:
    """Cookie nur bei explizitem ?lang= setzen."""
    return (request.query_params.get("lang") or "").strip().lower() == lang
