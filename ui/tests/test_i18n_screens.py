#!/usr/bin/env python3
"""Screenshot-Beweis: Startseite in de/en/fr/es/ar (Chrome/CDP).

Erzeugt ui/screenshots/ui_lang_<code>.png und prüft Sprache, Richtung (RTL)
und die sichtbare Überschrift.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import urllib.request

import websocket

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")
PORT = 9246
LANGS = ("de", "en", "fr", "es", "ar")
EXPECT = {
    "de": ("Reise suchen", "ltr"),
    "en": ("Search for a trip", "ltr"),
    "fr": ("Rechercher un voyage", "ltr"),
    "es": ("Buscar un viaje", "ltr"),
    "ar": ("البحث عن رحلة", "rtl"),
}
ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
OUT = ROOT / "ui" / "screenshots"
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
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = subprocess.Popen([
        "/usr/bin/google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--window-size=1280,1200",
        "--user-data-dir=/tmp/opencode/cdp-i18n", "about:blank"],
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

        for idx, lang in enumerate(LANGS):
            expected_h1, expected_dir = EXPECT[lang]
            cdp(ws, 10 + idx, "Page.navigate", {"url": f"{BASE}/?lang={lang}"})
            time.sleep(1.8)
            state = evaljs(ws, """JSON.stringify({
                lang: document.documentElement.lang,
                dir: document.documentElement.dir,
                h1: (document.querySelector('h1')||{}).textContent||'',
                cssDir: getComputedStyle(document.body).direction,
                switcher: !!document.querySelector('.lang-switch'),
                cookie: document.cookie
            })""")
            check(bool(state and state.get("lang") == lang), f"{lang}: html lang",
                  str(state and state.get("lang")))
            check(bool(state and state.get("dir") == expected_dir), f"{lang}: dir={expected_dir}",
                  str(state and state.get("dir")))
            check(bool(state and expected_h1 in (state.get("h1") or "")), f"{lang}: H1 korrekt",
                  str(state and state.get("h1")))
            check(bool(state and state.get("switcher")), f"{lang}: Umschalter sichtbar")
            if lang == "ar":
                check(bool(state and state.get("cssDir") == "rtl"), "ar: CSS direction=rtl",
                      str(state and state.get("cssDir")))
            shot = cdp(ws, 40 + idx, "Page.captureScreenshot",
                       {"format": "png", "captureBeyondViewport": True})
            data = (shot.get("result") or {}).get("data")
            path = OUT / f"ui_lang_{lang}.png"
            if data:
                path.write_bytes(base64.b64decode(data))
            check(bool(data) and path.exists(), f"{lang}: Screenshot", str(path.name))

        failed = [label for ok, label in results if not ok]
        print(f"\nErgebnis: {len(results) - len(failed)}/{len(results)} Prüfungen bestanden")
        if failed:
            print("Fehlgeschlagen: " + "; ".join(failed))
        return 0 if not failed else 1
    finally:
        chrome.terminate()


if __name__ == "__main__":
    sys.exit(main())
