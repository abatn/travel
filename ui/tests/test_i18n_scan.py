#!/usr/bin/env python3
"""Guard-Test: keine deutschen Resttexte in en/fr/es/ar (HTTP, ohne Browser).

Startet eine Suche und lädt die wichtigsten Seiten je Sprache. Vor der Prüfung
werden Bereiche entfernt, die absichtlich Deutsch enthalten dürfen:
i18n-Datenblock, Sprachumschalter, Markenname, technische IDs und IATA-Codes.
Danach wird nach deutschen Stoppwörtern gesucht. Jeder Treffer ist ein FAIL.

Aufruf: python3 ui/tests/test_i18n_scan.py [BASE]
Exitcode 1, sobald ein Treffer gemeldet wird.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")
LANGS = ("en", "fr", "es", "ar")
PATHS = (
    "/",
    "/fluege",
    "/preisvergleich",
    "/alarms",
    "/impressum",
    "/datenschutz",
    "/llms.txt",
    "/.well-known/agent-payments.json",
    "/gibtsnicht",
)

# Deutsche Stoppwörter (Nomen groß, Verben/Floskeln klein). Wortgrenzen,
# Groß-/Kleinschreibung zählt.
STOPWORDS = (
    "Günstige", "Quellen", "gesperrt", "Flüge", "Fähren", "Kreuzfahrten",
    "deaktiviert", "nicht verfügbar", "Wir vermitteln", "Stand ", "Anzeige",
    "Partnerprogramm", "Begründung", "Suche", "Ergebnis", "Hinweis", "Dauer",
    "Kategorie", "Quelle", "Anbieter", "Preis", "Bündelung", "Günstigstes",
)

# Wörter, die in der Zielsprache legitim sind (Groß-/Kleinschreibung zählt).
ALLOW = {
    "en": {"Stand"},   # englisches Verb/Substantiv "stand"
    "fr": {"Stand", "Quelle"},  # "Quelle" als französisches Fragewort am Satzanfang
    "es": set(),
    "ar": set(),
}

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def _pattern(term: str) -> str:
    if term.endswith(" "):
        return re.escape(term.rstrip()) + r"\s"
    return rf"(?<!\w){re.escape(term)}(?!\w)"


GERMAN_RE = re.compile("|".join(_pattern(t) for t in STOPWORDS))


def clean(html: str) -> str:
    """Entfernt Bereiche, die absichtlich Deutsch enthalten dürfen."""
    # i18n-Datenblock (enthält alle Übersetzungen, u. a. die deutsche Quelle)
    html = re.sub(r'<script[^>]*id="i18n-data"[^>]*>.*?</script>', " ",
                  html, flags=re.S | re.I)
    # Sprachumschalter (zeigt die Sprachnamen, u. a. "Deutsch")
    html = re.sub(r'<div[^>]*class="[^"]*lang-switch[^"]*"[^>]*>.*?</div>', " ",
                  html, flags=re.S | re.I)
    # Markenname ist ein Eigenname und bleibt unübersetzt
    html = html.replace("Reise-Agent", " ")
    # technische IDs
    html = re.sub(r"\bfli_flights\b", " ", html)
    html = re.sub(r"\bmcp_http\b", " ", html)
    html = re.sub(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", " ", html)  # snake_case
    html = re.sub(r"\beip155:[^\s\"'<>]*", " ", html)
    # IATA-Codes (BER, FCO …) und andere reine Großbuchstaben-Kürzel
    html = re.sub(r"\b[A-Z]{3}\b", " ", html)
    return html


def scan_text(path: str, body: str) -> str:
    """JSON-Antworten: mehrsprachige Maps (z. B. description_i18n) entfernen.

    Diese Maps enthalten absichtlich alle Sprachen, also auch Deutsch.
    """
    if not path.endswith(".json"):
        return body
    try:
        data = json.loads(body)
    except ValueError:
        return body

    def strip(node):
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if not k.endswith("_i18n")}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node

    return json.dumps(strip(data), ensure_ascii=False)


def hits(text: str, lang: str) -> list[tuple[str, str]]:
    """Eindeutige Fundstellen (gleiches Wort + gleicher Kontext = ein Treffer)."""
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in GERMAN_RE.finditer(text):
        term = m.group(0).strip()
        if term in ALLOW.get(lang, ()):
            continue
        ctx = text[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")
        ctx = " ".join(ctx.split())
        if (term, ctx) in seen:
            continue
        seen.add((term, ctx))
        found.append((term, ctx))
    return found


def start_search() -> str:
    body = urllib.parse.urlencode({
        "origin": "BER", "destination": "FCO", "depart_date": "2026-11-20",
        "adults": "1", "currency": "EUR", "categories": "flights",
        "timeout_seconds": "25"}).encode()
    req = urllib.request.Request(f"{BASE}/api/search", data=body, method="POST",
                                 headers={"Cookie": "lang=en"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())["job_id"]


def wait_job(job: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/api/jobs/{job}", timeout=10) as resp:
                state = json.loads(resp.read().decode()).get("state")
        except Exception:
            return
        if state in ("done", "error"):
            return
        time.sleep(1.5)


def main() -> int:
    s = httpx.Client(timeout=45, follow_redirects=True)
    try:
        job = start_search()
    except Exception as exc:  # Server nicht erreichbar o. Ä.
        check(False, "Suche startet", str(exc))
        print(f"\nErgebnis: 0/1 Prüfungen bestanden")
        return 1
    check(bool(job), "Suche startet", job)
    wait_job(job)
    paths = PATHS[:6] + (f"/jobs/{job}", f"/jobs/{job}/detail/flights/0") + PATHS[6:]

    total_hits = 0
    per_term: dict[str, int] = {}
    for lang in LANGS:
        for path in paths:
            sep = "&" if "?" in path else "?"
            url = f"{BASE}{path}{sep}lang={lang}"
            try:
                r = s.get(url)
            except Exception as exc:
                check(False, f"{lang}: {path} erreichbar", str(exc))
                continue
            found = hits(clean(scan_text(path, r.text)), lang)
            total_hits += len(found)
            for term, _ in found:
                per_term[term] = per_term.get(term, 0) + 1
            if found:
                detail = f"{len(found)} Treffer"
                check(False, f"{lang}: {path} ohne deutsche Reste", detail)
                for term, ctx in found[:12]:
                    print(f"        [{term}] …{ctx}…")
                if len(found) > 12:
                    print(f"        … und {len(found) - 12} weitere Fundstellen")
            else:
                check(True, f"{lang}: {path} ohne deutsche Reste")

    failed = [label for ok, label in results if not ok]
    print(f"\nErgebnis: {len(results) - len(failed)}/{len(results)} Prüfungen bestanden")
    print(f"Deutsche Treffer: {total_hits} (eindeutige Fundstellen)")
    if per_term:
        print("Treffer je Wort: " + ", ".join(
            f"{w} ({n})" for w, n in sorted(per_term.items(), key=lambda x: (-x[1], x[0]))))
    if failed:
        print("Fehlgeschlagen: " + "; ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
