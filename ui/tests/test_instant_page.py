#!/usr/bin/env python3
"""Regressionstest: Seite SOFORT nach dem Absenden öffnen (kein F5 nötig).

Der Nutzer meldete: „Quellen werden vorbereitet …“ / „Fertig – 0/0 Quellen“ bis F5.
Der Test lädt die Ergebnisseite unmittelbar nach dem POST und prüft, dass
  * die Quellenzeilen von Anfang an da sind (oder vom JS erzeugt werden),
  * der Fortschritt hochzählt,
  * am Ende Tabelle + Badge gefüllt sind – ohne Neuladen.
"""
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import websocket

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")
PORT = 9233
results = []


def check(ok, label, detail=""):
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def cdp(ws, i, method, params=None):
    ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
    while True:
        d = json.loads(ws.recv())
        if d.get("id") == i:
            return d


def evaljs(ws, expr):
    for _ in range(5):
        res = cdp(ws, 7, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
        payload = (res.get("result") or {}).get("result") or {}
        if "value" in payload:
            return json.loads(payload["value"])
        time.sleep(0.4)
    return None


def main():
    body = urllib.parse.urlencode({
        "origin": "TUN", "destination": "ORY", "depart_date": "2026-10-30",
        "return_date": "2026-11-15", "adults": "1", "currency": "EUR",
        "categories": "flights", "timeout_seconds": "40"}).encode()
    req = urllib.request.Request(BASE + "/api/search", data=body, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        job = json.loads(r.read().decode())["job_id"]
    print(f"Job: {job}")

    chrome = subprocess.Popen([
        "/usr/bin/google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--user-data-dir=/tmp/opencode/cdp-instant", "about:blank"],
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
        # sofort öffnen – wie nach dem Absenden des Formulars
        cdp(ws, 2, "Page.navigate", {"url": f"{BASE}/jobs/{job}?lang=de"})
        time.sleep(1.0)

        first = evaljs(ws, """JSON.stringify({
            rows: document.querySelectorAll('#live-status tr[data-source]').length,
            label: (document.getElementById('progress-label')||{}).textContent||''
        })""")
        print("  direkt nach dem Laden:", first)
        check(first and first["rows"] >= 1, "Quellenzeilen sofort vorhanden",
              f"{first['rows'] if first else 0} Zeilen")

        start = time.time()
        while time.time() - start < 90:
            with urllib.request.urlopen(f"{BASE}/api/jobs/{job}", timeout=10) as r:
                snap = json.loads(r.read().decode())
            if snap.get("state") == "done":
                break
            time.sleep(1)
        time.sleep(3)

        final = evaljs(ws, """JSON.stringify({
            loads: sessionStorage.getItem('__loads')||'1',
            rows: document.querySelectorAll('#live-status tr[data-source]').length,
            waiting: document.querySelectorAll('#live-status td.st').length
                     && Array.from(document.querySelectorAll('#live-status td.st'))
                        .filter(td => td.textContent.trim() === 'wartet').length,
            priceRows: document.querySelectorAll('table[id^="tbl-"] tbody tr td:first-child').length,
            badge: (document.querySelector('h2 .tag')||{}).textContent||'',
            center: (document.querySelector('#agent-svg .agent-count')||{}).textContent||'',
            nodes: document.querySelectorAll('#agent-svg .node').length,
            label: (document.getElementById('progress-label')||{}).textContent||''
        })""")
        print("  nach Abschluss:", final)
        check(final and final["rows"] >= 5, "alle Quellenzeilen angezeigt", str(final["rows"]))
        check(final and final["waiting"] == 0, "keine Zeile bleibt auf 'wartet'",
              str(final["waiting"]))
        check(final and final["priceRows"] >= 1, "Ergebnistabelle gefüllt",
              f"{final['priceRows']} Zeilen")
        check(final and "Angebote" in (final["badge"] or ""), "Badge gefüllt", str(final["badge"]))
        check(bool(final and final["nodes"] >= 5), "Netzwerk zeigt alle Quellen",
              str(final and final.get("nodes")))
        check(bool(final and final["center"]
                   and final["center"].split("/")[0] == final["center"].split("/")[-1]),
              "Zentrum zeigt n/n", str(final and final.get("center")))
        check(final and "Fertig" in (final["label"] or ""), "Status 'Fertig'", str(final["label"]))
        ws.close()
    finally:
        chrome.terminate()

    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 60)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
