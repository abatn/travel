#!/usr/bin/env python3
"""Dark/Light-Theme: Funktion, Persistenz, FOUC, Kontrast, Screenshots.

Startet bei Bedarf selbst einen lokalen Server (Port 8099). Aufruf:
    python3 ui/tests/test_theme.py [BASE_URL]

Geprüft werden:
  * Systempräferenz (prefers-color-scheme) ohne gespeicherte Wahl
  * manueller Toggle + localStorage-Persistenz + Reload
  * FOUC-Guard (Inline-Script vor dem Stylesheet, auch auf Rechtsseiten)
  * Kontrast (WCAG AA) für Text und Primary-Button in beiden Modi
  * SVG-Graph (Start + Ergebnis) und Live-Quellen-Tabelle in beiden Modi
  * Suche funktioniert in beiden Modi
  * Screenshots aller relevanten Seiten in Dark und Light
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ui" / "screenshots"
CDP_PORT = 9249
HERE = Path(__file__).resolve().parent
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")

results: list[tuple[bool, str]] = []
server_proc: subprocess.Popen | None = None


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def http_json(url: str, data: dict | None = None, timeout: int = 30):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET",
                                 headers={"User-Agent": "Mozilla/5.0 (compatible; theme-test/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()), r.status


def http_text(url: str) -> tuple[str, int]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; theme-test/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode(), r.status


def ensure_server() -> None:
    global BASE, server_proc
    try:
        http_text(BASE + "/health")
        print(f"Server läuft: {BASE}")
        return
    except Exception:
        pass
    BASE = "http://127.0.0.1:8099"
    py = ROOT / ".venv-x402" / "bin" / "python"
    env = dict(os.environ)
    keys = ROOT / "coinbase.txt"
    if keys.exists():
        lines = keys.read_text().splitlines()
        if len(lines) >= 4:
            env.setdefault("CDP_API_KEY_ID", lines[1].strip())
            env.setdefault("CDP_API_KEY_SECRET", lines[3].strip())
    server_proc = subprocess.Popen(
        [str(py if py.exists() else sys.executable), "-m", "uvicorn", "ui.app:app",
         "--host", "127.0.0.1", "--port", "8099", "--log-level", "warning"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Starte Testserver auf 8099 …")
    for _ in range(45):
        try:
            http_text(BASE + "/health")
            print(f"Server bereit: {BASE}")
            return
        except Exception:
            time.sleep(1)
    raise SystemExit("Server konnte nicht gestartet werden")


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.n = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                return msg

    def js(self, expr: str):
        res = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                             "awaitPromise": True})
        payload = (res.get("result") or {}).get("result") or {}
        if "value" not in payload:
            return None
        value = payload["value"]
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def goto(self, url: str, settle: float = 1.2) -> None:
        self.call("Page.navigate", {"url": url})
        for _ in range(60):
            if self.js("document.readyState") == "complete":
                break
            time.sleep(0.2)
        time.sleep(settle)

    def shot(self, path: Path, beyond: bool = True) -> bool:
        res = self.call("Page.captureScreenshot",
                        {"format": "png", "captureBeyondViewport": beyond,
                         "fromSurface": True})
        data = (res.get("result") or {}).get("data")
        if not data:
            return False
        path.write_bytes(base64.b64decode(data))
        return path.stat().st_size > 10_000

    def set_theme(self, theme: str | None, url: str, settle: float = 1.2) -> None:
        if theme is None:
            self.js("localStorage.removeItem('theme')")
        else:
            self.js(f"localStorage.setItem('theme', {json.dumps(theme)})")
        self.goto(url, settle)

    def emulate(self, scheme: str) -> None:
        self.call("Emulation.setEmulatedMedia", {
            "features": [{"name": "prefers-color-scheme", "value": scheme}]})


def theme_state(cdp: CDP) -> dict:
    return cdp.js("""JSON.stringify({
        theme: document.documentElement.getAttribute('data-theme'),
        pref: localStorage.getItem('theme'),
        colorScheme: document.documentElement.style.colorScheme,
        bodyBg: getComputedStyle(document.body).backgroundColor,
        bodyFg: getComputedStyle(document.body).color,
        toggle: !!document.getElementById('theme-toggle'),
        label: (document.getElementById('theme-toggle')||{}).getAttribute
               ? document.getElementById('theme-toggle').getAttribute('aria-label') : ''
    })""") or {}


def contrast(cdp: CDP) -> dict:
    return cdp.js("""(function(){
      function rgb(s){var m=(s||'').match(/[\\d.]+/g)||[0,0,0];return m.slice(0,3).map(Number);}
      function lum(c){return c.map(function(v){v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);})
        .reduce(function(a,v,i){return a+v*[0.2126,0.7152,0.0722][i];},0);}
      function ratio(a,b){var x=lum(a),y=lum(b);if(y>x){var t=x;x=y;y=t;}return (x+0.05)/(y+0.05);}
      var b=getComputedStyle(document.body), out={text:ratio(rgb(b.color),rgb(b.backgroundColor))};
      var btn=document.querySelector('button.primary');
      if(btn){var s=getComputedStyle(btn);out.button=ratio(rgb(s.color),rgb(s.backgroundColor));}
      return JSON.stringify(out);
    })()""") or {}


def create_job() -> str:
    data = {"origin": "BER", "destination": "FCO", "depart_date": "2026-11-05",
            "adults": "1", "currency": "EUR", "categories": "flights",
            "timeout_seconds": "40"}
    job, _ = http_json(BASE + "/api/search", data)
    job_id = job.get("job_id")
    if not job_id:
        raise SystemExit(f"Kein Job: {job}")
    print(f"Job: {job_id}")
    for _ in range(90):
        snap, _ = http_json(f"{BASE}/api/jobs/{job_id}")
        if snap.get("state") == "done":
            return job_id
        time.sleep(1)
    raise SystemExit("Job wurde nicht fertig")


PAGES = {
    "home": "/?lang=de",
    "fluege": "/fluege?lang=de",
    "preisvergleich": "/preisvergleich?lang=de",
    "alarms": "/alarms?lang=de",
    "impressum": "/impressum?lang=de",
}


def main() -> int:
    ensure_server()
    job = create_job()
    pages = dict(PAGES)
    pages["results"] = f"/jobs/{job}?lang=de"
    pages["detail"] = f"/jobs/{job}/detail/flights/0?lang=de"
    # Falls vorhanden: Detailseite eines Preisalarms mit abdecken.
    alarms_html, _ = http_text(BASE + "/alarms?lang=de")
    m = re.search(r"/alarms/([0-9a-f]{6,})", alarms_html)
    if m:
        pages["alarm"] = f"/alarms/{m.group(1)}?lang=de"

    # FOUC-Guard: Inline-Script muss vor dem CSS stehen (base + legal).
    for label, url in (("Startseite", BASE + "/?lang=de"),
                       ("Impressum", BASE + "/impressum?lang=de")):
        html, status = http_text(url)
        css = html.find('<link rel="stylesheet"')
        script = html.find("localStorage.getItem('theme')")
        check(status == 200 and script != -1 and css != -1 and script < css,
              f"FOUC-Guard {label}: Theme-Script vor CSS",
              f"script@{script} css@{css}")
        check('data-theme-dark' in html and 'data-theme-light' in html,
              f"FOUC-Guard {label}: theme-color-Varianten")

    chrome = subprocess.Popen([
        "/usr/bin/google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--remote-debugging-port={CDP_PORT}", "--remote-allow-origins=*",
        "--window-size=1280,1200",
        "--user-data-dir=/tmp/opencode/cdp-theme", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        target = None
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=2) as r:
                    tabs = json.loads(r.read().decode())
                target = next((t for t in tabs if t.get("type") == "page"), None)
                if target:
                    break
            except Exception:
                pass
            time.sleep(0.3)
        if not target:
            raise SystemExit("Chrome/CDP nicht erreichbar")

        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=40)
        cdp = CDP(ws)
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride",
                 {"width": 1280, "height": 1200, "deviceScaleFactor": 1, "mobile": False})
        cdp.goto(BASE + "/?lang=de")

        # --- Systempräferenz ---
        cdp.js("localStorage.removeItem('theme')")
        cdp.emulate("dark")
        cdp.goto(BASE + "/?lang=de")
        st = theme_state(cdp)
        check(st.get("theme") == "dark" and st.get("pref") is None,
              "System dunkel -> Dark (ohne gespeicherte Wahl)", str(st.get("theme")))
        cdp.emulate("light")
        cdp.goto(BASE + "/?lang=de")
        st = theme_state(cdp)
        check(st.get("theme") == "light" and st.get("colorScheme") == "light",
              "System hell -> Light (ohne gespeicherte Wahl)", str(st.get("theme")))

        # --- Toggle, Persistenz, Override ---
        cdp.set_theme("light", BASE + "/?lang=de")
        st = theme_state(cdp)
        check(st.get("theme") == "light" and st.get("toggle"), "Light gespeichert + Toggle vorhanden")
        label_light = st.get("label", "")
        cdp.js("document.getElementById('theme-toggle').click()")
        time.sleep(0.5)
        st = theme_state(cdp)
        check(st.get("theme") == "dark", "Klick wechselt zu Dark", str(st.get("theme")))
        check(st.get("pref") == "dark", "Wahl in localStorage gespeichert", str(st.get("pref")))
        check(bool(st.get("label")) and st.get("label") != label_light,
              "aria-label passt sich an", str(st.get("label")))
        cdp.goto(BASE + "/?lang=de")
        st = theme_state(cdp)
        check(st.get("theme") == "dark", "Reload behält Dark", str(st.get("theme")))
        cdp.emulate("light")
        cdp.goto(BASE + "/?lang=de")
        check(theme_state(cdp).get("theme") == "dark",
              "Explizite Wahl schlägt Systemeinstellung")
        cdp.js("document.getElementById('theme-toggle').click()")
        time.sleep(0.4)
        check(theme_state(cdp).get("theme") == "light", "Klick wechselt zurück zu Light")

        # --- Kontrast (auf der Startseite mit Primary-Button) ---
        for mode in ("dark", "light"):
            cdp.emulate(mode)
            cdp.set_theme(mode, BASE + "/?lang=de")
            c = contrast(cdp)
            check(c.get("text", 0) >= 4.5, f"{mode}: Textkontrast >= 4.5", f"{c.get('text', 0):.2f}")
            check(c.get("button", 0) >= 4.5, f"{mode}: Buttonkontrast >= 4.5",
                  f"{c.get('button', 0):.2f}")

        # --- Screenshots + Seitenprüfungen ---
        OUT.mkdir(parents=True, exist_ok=True)
        colors: dict[str, dict] = {"dark": {}, "light": {}}
        for mode in ("dark", "light"):
            cdp.emulate(mode)
            for name, path in pages.items():
                cdp.set_theme(mode, BASE + path, settle=1.6)
                st = theme_state(cdp)
                bg = st.get("bodyBg")
                ok = st.get("theme") == mode and st.get("toggle") and bg
                check(bool(ok), f"{mode}/{name}: Theme + Toggle", f"{st.get('theme')} {bg}")
                shot_name = f"theme_{mode}_{name}.png"
                check(cdp.shot(OUT / shot_name), f"{mode}/{name}: Screenshot", shot_name)
                colors[mode][name] = bg

                if name == "results":
                    graph = cdp.js("""JSON.stringify({
                        nodes: document.querySelectorAll('#agent-svg .node').length,
                        rows: document.querySelectorAll('.live-table tbody tr').length,
                        gradient: (function(){var s=document.querySelector('#agentGrad stop');
                          return s ? getComputedStyle(s).stopColor : '';})(),
                        nodeFill: (function(){var n=document.querySelector('#agent-svg .node rect');
                          return n ? getComputedStyle(n).fill : '';})(),
                        okColor: (function(){var e=document.querySelector('.st.ok')||document.querySelector('.st');
                          return e ? getComputedStyle(e).color : '';})()
                    })""") or {}
                    check(graph.get("nodes", 0) >= 1, f"{mode}/results: Graph-Knoten",
                          str(graph.get("nodes")))
                    check(graph.get("rows", 0) >= 1, f"{mode}/results: Live-Tabelle gefüllt",
                          str(graph.get("rows")))
                    colors[mode]["gradient"] = graph.get("gradient")
                    colors[mode]["nodeFill"] = graph.get("nodeFill")
                    colors[mode]["okColor"] = graph.get("okColor")

                if name == "home":
                    home = cdp.js("""JSON.stringify({
                        nodes: document.querySelectorAll('#home-agent-svg .home-node').length,
                        nodeFill: (function(){var n=document.querySelector('#home-agent-svg .home-node rect');
                          return n ? getComputedStyle(n).fill : '';})()
                    })""") or {}
                    check(home.get("nodes", 0) >= 4, f"{mode}/home: Schaubild-Knoten",
                          str(home.get("nodes")))
                    colors[mode]["homeFill"] = home.get("nodeFill")

        check(colors["dark"].get("gradient") != colors["light"].get("gradient"),
              "SVG-Verlauf folgt dem Theme",
              f"{colors['dark'].get('gradient')} / {colors['light'].get('gradient')}")
        check(colors["dark"].get("nodeFill") != colors["light"].get("nodeFill"),
              "Graph-Knoten folgt dem Theme",
              f"{colors['dark'].get('nodeFill')} / {colors['light'].get('nodeFill')}")
        check(colors["dark"].get("homeFill") != colors["light"].get("homeFill"),
              "Startseiten-Schaubild folgt dem Theme",
              f"{colors['dark'].get('homeFill')} / {colors['light'].get('homeFill')}")
        check(colors["dark"].get("okColor") != colors["light"].get("okColor"),
              "Live-Statusfarbe folgt dem Theme",
              f"{colors['dark'].get('okColor')} / {colors['light'].get('okColor')}")

        # --- RTL + Toggle auf Arabisch ---
        cdp.set_theme("light", BASE + "/impressum?lang=ar")
        rtl = cdp.js("""JSON.stringify({
            dir: document.documentElement.dir,
            theme: document.documentElement.getAttribute('data-theme'),
            toggle: !!document.getElementById('theme-toggle'),
            label: (document.getElementById('theme-toggle')||{}).getAttribute
                   ? document.getElementById('theme-toggle').getAttribute('aria-label') : ''
        })""") or {}
        check(rtl.get("dir") == "rtl" and rtl.get("theme") == "light" and rtl.get("toggle"),
              "Arabisch/RTL: Light + Toggle", str(rtl))
        check(cdp.shot(OUT / "theme_light_impressum_ar.png", beyond=False),
              "Screenshot RTL-Impressum", "theme_light_impressum_ar.png")

        # --- Suche in beiden Modi ---
        for mode, path in (("dark", "/?lang=de"), ("light", "/fluege?lang=de")):
            cdp.set_theme(mode, BASE + path)
            cdp.js("""(function(){
                var f=document.getElementById('searchform'); if(!f) return 'noform';
                f.querySelector('[name=origin]').value='BER';
                f.querySelector('[name=destination]').value='FCO';
                f.querySelector('[name=depart_date]').value='2026-11-05';
                if (f.requestSubmit) f.requestSubmit(); else f.submit();
                return 'ok';
            })()""")
            ok = False
            for _ in range(60):
                loc = cdp.js("location.pathname") or ""
                if str(loc).startswith("/jobs/"):
                    ok = True
                    break
                time.sleep(0.5)
            check(ok, f"Suche funktioniert im {mode}en Modus", str(cdp.js("location.pathname")))

        ws.close()
    finally:
        chrome.terminate()
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()

    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 64)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
