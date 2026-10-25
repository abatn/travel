#!/usr/bin/env python3
"""Browser-Test: kein Layout-Springen, kein Reload, Ergebnisse erscheinen automatisch.

Misst im echten Browser (Chrome DevTools Protocol):
  * Anzahl der Seitenaufrufe (muss 1 sein – kein Reload während der Suche)
  * Höhe des Live-Bereichs über die Laufzeit (darf nicht springen)
  * am Ende: Ergebnistabelle gefüllt, Fortschrittsbalken 100 %

Aufruf: python3 ui/tests/test_live_stability.py [BASE_URL]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import websocket

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")
PORT = 9231
results: list[tuple[bool, str]] = []

INJECT = """
(function () {
  var n = parseInt(sessionStorage.getItem('__loads') || '0', 10) + 1;
  sessionStorage.setItem('__loads', String(n));
  var log = [];
  try { log = JSON.parse(sessionStorage.getItem('__hlog') || '[]'); } catch (e) { log = []; }
  log.push({t: Date.now(), kind: 'load', h: 0});
  sessionStorage.setItem('__hlog', JSON.stringify(log.slice(-600)));
})();
"""


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
    body = urllib.parse.urlencode({
        "origin": "BER", "destination": "FCO", "depart_date": "2026-11-05",
        "adults": "1", "currency": "EUR", "categories": "flights",
        "timeout_seconds": "40"}).encode()
    req = urllib.request.Request(BASE + "/api/search", data=body, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        job = json.loads(r.read().decode())["job_id"]
    print(f"Job: {job}")

    chrome = subprocess.Popen([
        "/usr/bin/google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--user-data-dir=/tmp/opencode/cdp-live", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    heights: list[int] = []
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
            time.sleep(0.5)
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
        cdp(ws, 1, "Page.enable")
        cdp(ws, 2, "Page.addScriptToEvaluateOnNewDocument", {"source": INJECT})
        cdp(ws, 3, "Page.navigate", {"url": f"{BASE}/jobs/{job}?lang=de"})
        time.sleep(1.2)          # Navigationskontext abwarten (sonst kein Ergebnis)

        # Höhe während der Laufzeit messen
        expr = ("JSON.stringify({h: Math.round((document.getElementById('livebox')||{})"
                ".offsetHeight||0), state: document.body.dataset.state||''})")
        start = time.time()
        while time.time() - start < 60:
            res = cdp(ws, 4, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
            payload = (res.get("result") or {}).get("result") or {}
            if "value" not in payload:      # Kontext gewechselt -> nächster Versuch
                time.sleep(0.5)
                continue
            v = json.loads(payload["value"])
            if v["h"]:
                heights.append(v["h"])
            with urllib.request.urlopen(f"{BASE}/api/jobs/{job}", timeout=10) as r:
                snap = json.loads(r.read().decode())
            if snap.get("state") == "done":
                break
            time.sleep(0.8)
        time.sleep(2.5)

        # Endzustand prüfen
        final_expr = """JSON.stringify({
          loads: sessionStorage.getItem('__loads'),
          priceRows: document.querySelectorAll('table[id^="tbl-"] tbody tr td:first-child').length,
          badge: (document.querySelector('h2 .tag') || {}).textContent || '',
          center: (document.querySelector('#agent-svg .agent-count')||{}).textContent || '',
          nodes: document.querySelectorAll('#agent-svg .node').length,
          label: (document.getElementById('progress-label')||{}).textContent || ''
        })"""
        res = cdp(ws, 5, "Runtime.evaluate", {"expression": final_expr, "returnByValue": True})
        payload = (res.get("result") or {}).get("result") or {}
        if "value" not in payload:
            raise RuntimeError(f"DOM-Abfrage fehlgeschlagen: {json.dumps(res)[:200]}")
        final = json.loads(payload["value"])
        ws.close()
    finally:
        chrome.terminate()

    span = (max(heights) - min(heights)) if heights else 0
    print(f"  Messpunkte: {len(heights)}, Höhe min={min(heights) if heights else 0} "
          f"max={max(heights) if heights else 0} Spanne={span} px")
    check(final["loads"] in ("1", 1), "genau ein Seitenaufruf (kein Reload)", str(final["loads"]))
    check(span <= 8, "Live-Bereich behält seine Höhe (kein Springen)", f"{span} px")
    check(final["priceRows"] >= 1, "Ergebnistabelle automatisch gefüllt",
          f"{final['priceRows']} Zeilen")
    check(final["nodes"] >= 5, "Netzwerk zeigt alle Quellen", str(final["nodes"]))
    check("/" in str(final["center"]), "Zentrum zeigt den Zähler", str(final["center"]))
    check("Fertig" in (final["label"] or ""), "Statusmeldung 'Fertig'", str(final["label"])[:50])
    check("Angebote" in (final["badge"] or ""), "Badge zeigt die Angebotszahl", str(final["badge"]))

    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 62)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
