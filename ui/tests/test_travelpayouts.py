#!/usr/bin/env python3
"""Travelpayouts/Aviasales-Tracking: Skript im <head>, Marker, Datenschutz.

Prüft ohne Browser (httpx):
  * Emerald-Script (emrldtp.cc/NTg5MzUy.js?t=589352) steht im <head> aller Seiten
  * Auf allen fünf Sprachen (de/en/fr/es/ar) vorhanden
  * Datenschutz nennt Travelpayouts/emrldtp.cc und die Cookies
  * affiliate/config.yaml trägt den Marker 793886

Aufruf: python3 ui/tests/test_travelpayouts.py [BASE_URL]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
import yaml

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8095").rstrip("/")
ROOT = Path(__file__).resolve().parents[2]
LANGS = ("de", "en", "fr", "es", "ar")
SCRIPT = "emrldtp.cc/NTg5MzUy.js?t=589352"
MARKER = "793886"
PAGES = ("/", "/preisvergleich", "/datenschutz", "/impressum")
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def head_of(html: str) -> str:
    m = re.search(r"<head>[\s\S]*?</head>", html, re.I)
    return m.group(0) if m else ""


def main() -> int:
    with httpx.Client(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (reise-agent-tests)"},
    ) as client:
        for path in PAGES:
            r = client.get(f"{BASE}{path}?lang=de")
            head = head_of(r.text)
            check(r.status_code == 200, f"{path} antwortet 200", str(r.status_code))
            check(SCRIPT in head, f"{path}: Tracking-Skript im <head>",
                  SCRIPT if SCRIPT not in head else "")
            check("nowprocket" in head, f"{path}: Emerald-Script-Attribute erhalten",
                  "nowprocket fehlt" if "nowprocket" not in head else "")

        for lang in LANGS:
            r = client.get(f"{BASE}/?lang={lang}")
            check(SCRIPT in head_of(r.text), f"Startseite {lang}: Tracking-Skript")
            r = client.get(f"{BASE}/datenschutz?lang={lang}")
            privacy = r.text
            check("emrldtp.cc" in privacy and "Travelpayouts" in privacy,
                  f"Datenschutz {lang}: Travelpayouts/emrldtp.cc genannt",
                  "Text fehlt" if not ("emrldtp.cc" in privacy and "Travelpayouts" in privacy) else "")

        # Fehlerseiten sind jetzt vollwertige Seiten (frueher rohe HTML-Fragmente).
        for path in ("/jobs/unbekannt/detail/flights/0", "/alarms/unbekannt",
                     "/gibtsnicht"):
            r = client.get(f"{BASE}{path}?lang=de")
            check(r.status_code == 404, f"{path}: 404", str(r.status_code))
            check(SCRIPT in head_of(r.text), f"{path}: 404-Seite hat Tracking-Skript")
        for lang in LANGS:
            r = client.get(f"{BASE}/alarms/unbekannt?lang={lang}")
            check(SCRIPT in head_of(r.text), f"Fehlerseite {lang}: Tracking-Skript")

    cfg = yaml.safe_load((ROOT / "affiliate" / "config.yaml").read_text(encoding="utf-8"))
    tp = (cfg.get("partners") or {}).get("travelpayouts") or {}
    got = str(tp.get("id", ""))
    check(got == MARKER, "affiliate/config.yaml: partners.travelpayouts.id = Marker", got)
    tpl = str(tp.get("link_template", ""))
    check(tpl == "", "link_template bleibt leer (kein geratenes Netzwerk-Format)", tpl)

    ok = all(c for c, _ in results)
    print(f"\n{sum(1 for c, _ in results if c)}/{len(results)} OK")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
