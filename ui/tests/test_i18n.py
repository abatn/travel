#!/usr/bin/env python3
"""HTTP-Tests der Mehrsprachigkeit (de/en/fr/es/ar) ohne Browser.

Prüft Startseite, Rechtsseiten, llms.txt, Discovery, Cookie/Header-Auflösung,
RTL und die Suche als Regression.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")
LANGS = ("de", "en", "fr", "es", "ar")
H1 = {
    "de": "Reise suchen",
    "en": "Search for a trip",
    "fr": "Rechercher un voyage",
    "es": "Buscar un viaje",
    "ar": "البحث عن رحلة",
}
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def main() -> int:
    s = httpx.Client(timeout=30, follow_redirects=True)
    for lang in LANGS:
        r = s.get(f"{BASE}/?lang={lang}")
        check(r.status_code == 200, f"{lang}: Startseite 200", str(r.status_code))
        check(f'<html lang="{lang}"' in r.text, f"{lang}: html lang")
        check(f'dir="{"rtl" if lang == "ar" else "ltr"}"' in r.text, f"{lang}: dir")
        check(f"<h1>{H1[lang]}</h1>" in r.text, f"{lang}: H1 übersetzt")
        check("lang-switch" in r.text, f"{lang}: Sprachumschalter sichtbar")
        check(f"lang={lang}" in r.text, f"{lang}: Link auf eigene Sprache")

        # Rechtsseiten
        for path, expect in (("/impressum", "legal.imprint"), ("/datenschutz", "legal.privacy")):
            lr = s.get(f"{BASE}{path}?lang={lang}")
            check(lr.status_code == 200, f"{lang}: {path} 200", str(lr.status_code))
            if lang != "de":
                check("Translation for information" in lr.text or "ترجمة" in lr.text
                      or "Traduction" in lr.text or "Traducción" in lr.text,
                      f"{lang}: Hinweis auf verbindliche deutsche Fassung")
        # llms.txt
        ll = s.get(f"{BASE}/llms.txt?lang={lang}")
        check(ll.status_code == 200, f"{lang}: llms.txt 200", str(ll.status_code))
        if lang != "de":
            check(ll.text.startswith("# Reise-Agent ("), f"{lang}: llms.txt Intro übersetzt")

    # Cookie wird nur bei ?lang= gesetzt
    r1 = s.get(f"{BASE}/?lang=es", headers={"Accept-Language": "de"})
    check("lang=es" in r1.headers.get("set-cookie", ""), "Cookie aus ?lang= gesetzt")
    r2 = s.get(f"{BASE}/")
    check("set-cookie" not in {k.lower() for k in r2.headers}, "kein Cookie ohne ?lang=")

    # Accept-Language greift ohne Cookie/Query
    r3 = httpx.get(f"{BASE}/", headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
                   timeout=30)
    check('<html lang="fr"' in r3.text, "Accept-Language → fr")

    # Cache darf nicht öffentlich sein (sprachabhängig)
    check("private" in r1.headers.get("cache-control", ""), "Cache-Control private")

    # Discovery
    d = s.get(f"{BASE}/.well-known/agent-payments.json").json()
    check(d.get("languages") == list(LANGS), "Discovery: languages", str(d.get("languages")))
    desc = d.get("description_i18n") or {}
    check(all(desc.get(c) for c in LANGS), "Discovery: Beschreibung je Sprache")
    check(len({desc.get(c) for c in LANGS}) == len(LANGS), "Discovery: Beschreibungen verschieden")

    # Regression: Suche mit Sprach-Cookie
    body = urllib.parse.urlencode({
        "origin": "BER", "destination": "FCO", "depart_date": "2026-11-20",
        "adults": "1", "currency": "EUR", "categories": "flights",
        "timeout_seconds": "25"}).encode()
    req = urllib.request.Request(f"{BASE}/api/search", data=body, method="POST",
                                 headers={"Cookie": "lang=fr"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        job = json.loads(resp.read().decode())["job_id"]
    check(bool(job), "Suche startet mit Sprach-Cookie", job)
    jr = s.get(f"{BASE}/jobs/{job}?lang=fr")
    check(jr.status_code == 200, "Ergebnisseite 200", str(jr.status_code))
    check('<html lang="fr"' in jr.text, "Ergebnisseite übernimmt Sprache")
    check("Recherche" in jr.text or "résultats" in jr.text.lower() or "Ergebnisse" not in jr.text,
          "Ergebnisseite übersetzt")

    failed = [label for ok, label in results if not ok]
    print(f"\nErgebnis: {len(results) - len(failed)}/{len(results)} Prüfungen bestanden")
    if failed:
        print("Fehlgeschlagen: " + "; ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
