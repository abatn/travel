#!/usr/bin/env python3
"""End-to-End-Test: Affiliate-Links, Disclosure und Weiterleitung über die UI.

Startet zwei eigene UI-Instanzen:
  A) mit Testkonfiguration (Demo-Partner, fiktive ID) -> Link wird getaggt
  B) mit Produktionskonfiguration (keine ID)          -> Link bleibt ungetaggt

Geprüft wird je Instanz der komplette Fluss: Suche starten -> Ergebnis ->
Detailseite -> Buchungslink + Kennzeichnung + Rechtshinweis.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "affiliate"))
import legal  # noqa: E402

PY = sys.executable
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def start_server(port: int, affiliate_config: str | None) -> subprocess.Popen:
    env = dict(os.environ)
    env["AFFILIATE_CONFIG"] = affiliate_config if affiliate_config else os.path.join(
        ROOT, "affiliate", "config.yaml")
    proc = subprocess.Popen([PY, "-m", "uvicorn", "ui.app:app", "--host", "127.0.0.1",
                             "--port", str(port), "--log-level", "warning"],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            if requests.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return proc
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Server auf Port {port} nicht erreichbar")


def run_search(base: str) -> str:
    r = requests.post(base + "/api/search", data={
        "origin": "BER", "destination": "FCO", "city": "Rome",
        "depart_date": "2026-10-31", "return_date": "", "adults": "1",
        "children": "0", "currency": "EUR", "max_stops": "one_stop",
        "categories": ["flights"], "timeout_seconds": "45",
    }, timeout=30)
    job_id = r.json()["job_id"]
    for _ in range(200):
        snap = requests.get(f"{base}/api/jobs/{job_id}", timeout=30).json()
        if snap.get("state") == "done":
            return job_id
        time.sleep(2)
    raise RuntimeError("Suche nicht abgeschlossen")


def main() -> int:
    demo_cfg = os.path.join(ROOT, "affiliate", "tests", "test_config_ui.yaml")
    a = start_server(8091, demo_cfg)
    b = start_server(8092, None)
    try:
        print("A) Mit Test-Partnerkennung (fiktive ID)")
        job_a = run_search("http://127.0.0.1:8091")
        page = requests.get(f"http://127.0.0.1:8091/jobs/{job_a}/detail/flights/0",
                            timeout=30).text
        check("Anzeige" in page and "Affiliate-Link" in page,
              "Disclosure 'Anzeige · Affiliate-Link' ist sichtbar")
        check("rel=\"sponsored" in page, "Buchungslink hat rel=sponsored")
        m = re.search(r'href="(https?://[^"]+)"[^>]*rel="sponsored', page)
        check(bool(m), "Affiliate-Link ist der sichtbare Buchungslink",
              (m.group(1)[:80] if m else "keiner"))
        check(bool(m) and "TESTMARKER-0000" in m.group(1),
              "Link enthält die konfigurierte Kennung")
        check("TESTNETZWERK" in page, "Netzwerk wird ausgewiesen")
        check("nicht Reiseveranstalter" in page,
              "Rechtshinweis: keine Veranstalterrolle")
        check("keine Zahlung" in page.lower() or "keine zahlung" in page.lower(),
              "Hinweis: keine Zahlung über die Oberfläche")
        check("Link geprüft" in page or "konnte nicht verifiziert werden" in page,
              "Erreichbarkeitsprüfung wird ausgewiesen")
        findings = legal.ui_guard(page)
        check(not findings, "Keine Leitplanken-Verstöße im gerenderten HTML",
              "; ".join(findings)[:140])

        print("\nB) Ohne Partnerkennung (Produktionskonfiguration)")
        job_b = run_search("http://127.0.0.1:8092")
        page_b = requests.get(f"http://127.0.0.1:8092/jobs/{job_b}/detail/flights/0",
                              timeout=30).text
        check("Anzeige · Affiliate-Link" not in page_b,
              "Kein Affiliate-Badge ohne konfigurierte ID")
        check("rel=\"sponsored" not in page_b, "Kein rel=sponsored ohne Kennung")
        check("Kein Affiliate-Link" in page_b or "keine ID" in page_b,
              "Grund wird genannt (keine ID / kein Partnerprogramm)",
              (re.search(r"Kein Affiliate-Link: ([^<]{0,90})", page_b) or
               re.match(r"", "")) and "" or "siehe Seite")
        check("nicht Reiseveranstalter" in page_b,
              "Rechtshinweis ist auch ohne Affiliate-Link vorhanden")
        findings_b = legal.ui_guard(page_b)
        check(not findings_b, "Keine Leitplanken-Verstöße (ohne Kennung)",
              "; ".join(findings_b)[:140])

        print("\nC) Affiliate-Status der Oberfläche")
        st = requests.get("http://127.0.0.1:8091/api/affiliate", timeout=20)
        if st.status_code == 200:
            data = st.json()
            check(any(p.get("network", "").startswith("TESTNETZWERK")
                      for p in data.get("partners", [])) or data.get("demo_active") is True,
                  "Testkennung ist als aktiv ausgewiesen")
        else:
            check(False, "Affiliate-Status abrufbar", f"HTTP {st.status_code}")
    finally:
        a.terminate()
        b.terminate()

    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 62)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
