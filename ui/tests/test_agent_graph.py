#!/usr/bin/env python3
"""Browser-Test der Agenten-Netzwerk-Animation (Chrome DevTools Protocol).

Prüft:
  * SVG-Graph vorhanden, ein Knoten/Kante je Quelle, Zentrum mit Zähler
  * Status wandert live (waiting -> ok/error/skipped), keine Zeile bleibt „waiting“
  * wartende Kanten haben die Fluss-Animation (CSS animation-name = "flow")
  * „Datenpakete“ existieren (offset-path) – oder sind sauber ausgeblendet
  * Höhe des Graphen bleibt konstant (kein Layout-Springen)
  * nach Abschluss: Zentrum zeigt n/n, Kanten sind durchgezogen grün/rot/gelb

Aufruf: python3 ui/tests/test_agent_graph.py [BASE_URL]
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
PORT = 9241
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def cdp(ws, i, method, params=None):
    ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
    while True:
        d = json.loads(ws.recv())
        if d.get("id") == i:
            return d


def evaljs(ws, expr):
    for _ in range(6):
        res = cdp(ws, 9, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
        payload = (res.get("result") or {}).get("result") or {}
        if "value" in payload:
            return json.loads(payload["value"])
        time.sleep(0.3)
    return None


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
        "--user-data-dir=/tmp/opencode/cdp-graph", "about:blank"],
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
            time.sleep(0.4)
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
        cdp(ws, 1, "Page.enable")
        cdp(ws, 2, "Page.navigate", {"url": f"{BASE}/jobs/{job}"})
        time.sleep(1.2)

        first = evaljs(ws, """JSON.stringify({
            svg: !!document.getElementById('agent-svg'),
            nodes: document.querySelectorAll('#agent-svg .node').length,
            edges: document.querySelectorAll('#agent-svg .edge').length,
            packets: document.querySelectorAll('#agent-svg .packet').length,
            center: (document.querySelector('#agent-svg .agent-count')||{}).textContent||'',
            waitingAnim: (function(){ var e=document.querySelector('#agent-svg .edge.waiting');
                            return e ? getComputedStyle(e).animationName : ''; })(),
            height: Math.round((document.getElementById('agent-graph')||{}).offsetHeight||0),
            packetPath: (function(){ var p=document.querySelector('#agent-svg .packet');
                          return p ? (p.style.offsetPath||'') : ''; })()
        })""")
        print("  direkt nach dem Laden:", first)
        check(bool(first and first["svg"]), "SVG-Graph vorhanden")
        check(bool(first and first["nodes"] >= 1), "Quellen-Knoten vorhanden",
              f"{first['nodes'] if first else 0}")
        check(bool(first and first["edges"] >= 1), "Verbindungen vorhanden",
              f"{first['edges'] if first else 0}")
        check(bool(first and first["nodes"] == first["edges"]),
              "ein Knoten = eine Kante", f"{first['nodes']}/{first['edges']}")
        check('/' in str(first and first["center"]), "Zentrum zeigt Zähler",
              str(first and first["center"]))
        check((first or {}).get("waitingAnim") == "flow",
              "wartende Kante ist animiert (flow)", str((first or {}).get("waitingAnim")))
        check((first or {}).get("packets", 0) >= 1, "Datenpakete vorhanden",
              str((first or {}).get("packets")))

        start = time.time()
        while time.time() - start < 90:
            with urllib.request.urlopen(f"{BASE}/api/jobs/{job}", timeout=10) as r:
                snap = json.loads(r.read().decode())
            h = evaljs(ws, "JSON.stringify(Math.round((document.getElementById('agent-graph')||{}).offsetHeight||0))")
            if h:
                heights.append(h)
            if snap.get("state") == "done":
                break
            time.sleep(1.2)
        time.sleep(1.5)

        final = evaljs(ws, """JSON.stringify({
            nodes: document.querySelectorAll('#agent-svg .node').length,
            edges: document.querySelectorAll('#agent-svg .edge').length,
            waiting: document.querySelectorAll('#agent-svg .edge.waiting').length,
            ok: document.querySelectorAll('#agent-svg .edge.ok').length,
            error: document.querySelectorAll('#agent-svg .edge.error').length,
            skipped: document.querySelectorAll('#agent-svg .edge.skipped').length,
            center: (document.querySelector('#agent-svg .agent-count')||{}).textContent||'',
            label: (document.getElementById('progress-label')||{}).textContent||'',
            haloDone: !!(document.querySelector('#agent-svg .halo')||{}).classList && 
                      document.querySelector('#agent-svg .halo').classList.contains('done')
        })""")
        print("  nach Abschluss:", final)
        check((final or {}).get("waiting") == 0, "keine Kante bleibt im Wartezustand",
              str((final or {}).get("waiting")))
        check(((final or {}).get("ok", 0) + (final or {}).get("error", 0)
               + (final or {}).get("skipped", 0)) >= 1,
              "Kanten haben Endstatus",
              f"ok={final.get('ok')} err={final.get('error')} skip={final.get('skipped')}")
        check(str((final or {}).get("center", "")).split("/")[0]
              == str((final or {}).get("center", "")).split("/")[-1],
              "Zentrum zeigt n/n", str((final or {}).get("center")))
        check("Fertig" in str((final or {}).get("label")), "Status 'Fertig'",
              str((final or {}).get("label"))[:60])
        check(bool((final or {}).get("haloDone")), "Pulsieren beendet (halo done)")
        span = (max(heights) - min(heights)) if heights else 0
        check(span <= 8, "Graphhöhe konstant (kein Springen)", f"{span} px")
        ws.close()
    finally:
        chrome.terminate()

    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 62)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
