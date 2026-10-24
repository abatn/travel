#!/usr/bin/env python3
"""Prüft die vier Kategorieseiten: Felder, Texte, Suche, Screenshots.

Jede Seite darf nur die Felder zeigen, die ihre Suchlogik verarbeitet.
Aufruf: python3 ui/tests/test_category_pages.py [BASE_URL]
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import httpx
import websocket

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")
PORT = 9247
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ui" / "screenshots"
results: list[tuple[bool, str]] = []

PAGES = {
    "fluege": {
        "fields": ["origin", "destination", "depart_date", "return_date", "adults",
                   "children", "max_stops", "currency"],
        "absent": ["ferry_origin", "cruise_origin", "hotel_stars", "city"],
        "form": {"origin": "BER", "destination": "FCO", "depart_date": "2026-11-20",
                 "adults": "1", "categories": "flights"},
    },
    "hotels": {
        "fields": ["city", "depart_date", "return_date", "adults", "children",
                   "hotel_stars", "currency"],
        "absent": ["origin", "destination", "ferry_origin", "cruise_origin", "max_stops"],
        "form": {"city": "Rom", "depart_date": "2026-11-20", "return_date": "2026-11-22",
                 "adults": "2", "categories": "hotels"},
    },
    "faehren": {
        "fields": ["ferry_origin", "ferry_destination", "depart_date", "adults",
                   "children", "currency"],
        "absent": ["origin", "destination", "max_stops", "hotel_stars", "cruise_origin"],
        "form": {"ferry_origin": "Ancona", "ferry_destination": "Igoumenitsa",
                 "depart_date": "2026-11-20", "adults": "1", "categories": "ferries"},
    },
    "kreuzfahrten": {
        "fields": ["cruise_origin", "cruise_destination", "depart_date", "adults",
                   "children", "currency"],
        "absent": ["origin", "destination", "max_stops", "hotel_stars", "ferry_origin"],
        "form": {"cruise_origin": "Hamburg", "cruise_destination": "Miami",
                 "depart_date": "2026-11-20", "adults": "2", "categories": "cruises"},
    },
}


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def cdp(ws, i, method, params=None):
    ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
    while True:
        d = json.loads(ws.recv())
        if d.get("id") == i:
            return d


def main() -> int:
    s = httpx.Client(timeout=30, follow_redirects=True)
    for slug, spec in PAGES.items():
        r = s.get(f"{BASE}/{slug}?lang=de")
        check(r.status_code == 200, f"{slug}: 200", str(r.status_code))
        html = r.text
        for field in spec["fields"]:
            check(f'name="{field}"' in html, f"{slug}: Feld {field}")
        for field in spec["absent"]:
            check(f'name="{field}"' not in html, f"{slug}: kein Feld {field}")
        check("Was diese Seite kann" in html, f"{slug}: Fähigkeiten-Text")
        check("Was sie nicht kann" in html, f"{slug}: Grenzen-Text")
        if slug in ("faehren", "kreuzfahrten"):
            check('value="BER"' not in html and 'value="FCO"' not in html,
                  f"{slug}: keine Flug-Defaults")

    # Suche je Kategorie starten (nur Job-Erzeugung, kein Warten auf Ergebnisse)
    for slug, spec in PAGES.items():
        body = urllib.parse.urlencode({**spec["form"], "timeout_seconds": "10"}).encode()
        req = urllib.request.Request(f"{BASE}/api/search", data=body, method="POST",
                                     headers={"User-Agent": "category-test/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                job = json.loads(resp.read().decode()).get("job_id")
        except Exception as exc:  # noqa: BLE001
            job = None
            detail = str(exc)[:80]
        else:
            detail = job or ""
        check(bool(job), f"{slug}: Suche startet", detail)

    # Screenshots
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = subprocess.Popen([
        "/usr/bin/google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--window-size=1280,1200",
        "--user-data-dir=/tmp/opencode/cdp-categories", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        target = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                    tabs = json.loads(r.read().decode())
                target = next((t for t in tabs if t.get("type") == "page"), None)
                if target:
                    break
            except Exception:
                pass
            time.sleep(0.4)
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
        cdp(ws, 1, "Page.enable")
        for i, slug in enumerate(PAGES, start=10):
            cdp(ws, i, "Page.navigate", {"url": f"{BASE}/{slug}?lang=de"})
            time.sleep(1.5)
            shot = cdp(ws, 30 + i, "Page.captureScreenshot",
                       {"format": "png", "captureBeyondViewport": True})
            data = (shot.get("result") or {}).get("data")
            path = OUT / f"ui_cat_{slug}.png"
            if data:
                path.write_bytes(base64.b64decode(data))
            check(bool(data) and path.exists(), f"{slug}: Screenshot", path.name)
    finally:
        chrome.terminate()

    failed = [label for ok, label in results if not ok]
    print(f"\nErgebnis: {len(results) - len(failed)}/{len(results)} Prüfungen bestanden")
    if failed:
        print("Fehlgeschlagen: " + "; ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
