#!/usr/bin/env python3
"""Browser-Test des Agenten-Schaubilds auf der Startseite (Chrome/CDP).

Prüft:
  * SVG vorhanden, 4 Kategorie-Knoten + 4 Verbindungen
  * Loop-Schleife mit Wahrnehmen/Planen/Handeln/Beobachten
  * Zentrum zeigt "Agent" + Status
  * Live-Status aus /api/status wird angewendet (waiting/ok/error)
  * wartende Kante ist animiert (CSS animation-name = flow)
  * Klick auf einen Knoten wählt die Kategorie im Formular
  * Suche funktioniert weiter (Weiterleitung auf /jobs/…, Ergebnis-Graph vorhanden)
  * Screenshot: ui/screenshots/ui_home_graph.png

Aufruf: python3 ui/tests/test_home_graph.py [BASE_URL]
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import websocket

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")
PORT = 9242
ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
SHOT = ROOT / "ui" / "screenshots" / "ui_home_graph.png"
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
    for _ in range(8):
        res = cdp(ws, 9, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
        payload = (res.get("result") or {}).get("result") or {}
        if "value" in payload:
            return json.loads(payload["value"])
        time.sleep(0.3)
    return None


def main() -> int:
    chrome = subprocess.Popen([
        "/usr/bin/google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--window-size=1280,1400",
        "--user-data-dir=/tmp/opencode/cdp-home", "about:blank"],
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
        cdp(ws, 2, "Runtime.enable")
        cdp(ws, 3, "Page.navigate", {"url": BASE + "/?lang=de"})
        time.sleep(1.5)
        # frischer Zustand: gemerkten Lauf aus früheren Testläufen entfernen
        evaljs(ws, "(function(){try{localStorage.clear()}catch(e){};return JSON.stringify(true)})()")
        cdp(ws, 4, "Page.reload", {"ignoreCache": True})
        time.sleep(2.0)

        first = None
        for _ in range(20):
            first = evaljs(ws, """JSON.stringify({
                svg: !!document.getElementById('home-agent-svg'),
                nodes: document.querySelectorAll('#home-agent-svg .home-node').length,
                edges: document.querySelectorAll('#home-agent-svg .home-edge').length,
                phases: Array.from(document.querySelectorAll('.home-phase')).map(t=>t.textContent),
                title: (document.querySelector('.home-center .title')||{}).textContent||'',
                mind: (document.querySelector('.home-center .mind')||{}).textContent||'',
                status: (document.getElementById('home-agent-status')||{}).textContent||'',
                classes: Array.from(document.querySelectorAll('.home-node')).map(n=>n.getAttribute('class')),
                flow: (function(){ var e=document.querySelector('.home-edge.waiting');
                         return e ? getComputedStyle(e).animationName : ''; })()
            })""")
            if first and "Quellen" in (first.get("mind") or ""):
                break
            time.sleep(0.5)
        print("  Startseite:", without_edges(first))
        check(bool(first and first["svg"]), "SVG-Schaubild vorhanden")
        check(bool(first and first["nodes"] == 4), "4 Kategorie-Knoten", str(first and first["nodes"]))
        check(bool(first and first["edges"] == 4), "4 Verbindungen", str(first and first["edges"]))
        check(bool(first and sorted(first["phases"]) == sorted(
            ["Wahrnehmen", "Planen", "Handeln", "Beobachten"])),
            "Loop-Schleife vollständig", str(first and first["phases"]))
        check(bool(first and first["title"] == "Agent"), "Zentrum: Agent", str(first and first["title"]))
        check(bool(first and "Quellen" in first["mind"]), "Zentrum zeigt Status",
              str(first and first["mind"]))
        check(bool(first and all(c.split()[1] in ("waiting", "ok", "error") for c in first["classes"])),
              "Status-Klassen gesetzt", str(first and first["classes"]))
        check((first or {}).get("flow") == "flow", "wartende Verbindung animiert",
              str((first or {}).get("flow")))

        # Screenshot
        SHOT.parent.mkdir(parents=True, exist_ok=True)
        shot = cdp(ws, 11, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
        data = (shot.get("result") or {}).get("data")
        if data:
            SHOT.write_bytes(base64.b64decode(data))
        check(bool(data) and SHOT.exists(), "Screenshot gespeichert", str(SHOT))

        # Interaktivität: Klick auf Hotels wählt die Kategorie
        clicked = evaljs(ws, """(function(){
            var node = document.querySelector('.home-node[data-cat="hotels"]');
            if (!node) return JSON.stringify({ok:false});
            node.dispatchEvent(new MouseEvent('click', {bubbles:true}));
            var box = document.querySelector('input[name="categories"][value="hotels"]');
            return JSON.stringify({ok: !!(box && box.checked), mind: (document.querySelector('.home-center .mind')||{}).textContent});
        })()""")
        check(bool(clicked and clicked.get("ok")), "Klick wählt Kategorie",
              str(clicked and clicked.get("mind")))

        # Regression: Suche starten -> Weiterleitung auf /jobs/…
        evaljs(ws, """(function(){
            document.querySelector('input[name="origin"]').value='BER';
            document.querySelector('input[name="destination"]').value='FCO';
            var d=document.querySelector('input[name="depart_date"]');
            d.value='2026-11-20';
            document.querySelectorAll('input[name="categories"]').forEach(c=>{c.checked=(c.value==='flights');});
            document.getElementById('searchform').requestSubmit();
            return JSON.stringify(true);
        })()""")
        start = time.time()
        navigated = None
        while time.time() - start < 60:
            navigated = evaljs(ws, "JSON.stringify({url: location.pathname, graph: !!document.getElementById('agent-svg')})")
            if navigated and navigated.get("url", "").startswith("/jobs/") and navigated.get("graph"):
                break
            time.sleep(1.0)
        check(bool(navigated and str(navigated.get("url", "")).startswith("/jobs/")),
              "Suche leitet weiter (/jobs/…)", str(navigated and navigated.get("url")))
        check(bool(navigated and navigated.get("graph")), "Ergebnisseite zeigt Agenten-Graph")

        failed = [label for ok, label in results if not ok]
        print(f"\nErgebnis: {len(results) - len(failed)}/{len(results)} Prüfungen bestanden")
        if failed:
            print("Fehlgeschlagen: " + ", ".join(failed))
        return 0 if not failed else 1
    finally:
        chrome.terminate()


def without_edges(d):
    if not d:
        return d
    return {k: v for k, v in d.items() if k != "edges"}


if __name__ == "__main__":
    sys.exit(main())
