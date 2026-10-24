#!/usr/bin/env python3
"""Beweist: leere legal.yaml -> noindex, vollständige -> indexierbar."""
from __future__ import annotations

import copy
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable


def _port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _wait(url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    raise RuntimeError(f"{url} nicht erreichbar")


@contextmanager
def serve(legal_path: Path, port: int):
    if not _port_free(port):
        raise RuntimeError(f"Port {port} belegt")
    env = dict(os.environ)
    env.update({
        "LEGAL_CONFIG": str(legal_path),
        "ATTEST_ENABLED": "0",
        "PYTHONPATH": str(ROOT),
    })
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "ui.app:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait(f"http://127.0.0.1:{port}/health")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


PLACEHOLDER = {
    "betreiber": {
        "name": "[Batnini Abdelkader]",
        "strasse": "[wildgansweg 34]",
        "plz_ort": "[70378 Stuttgart]",
        "land": "Deutschland",
        "email": "[deine@email.de]",
        "umsatzsteuer_id": '[USt-IdNr. oder "keine"]',
        "verantwortlich": "[Batnini Abdelkader]",
    },
    "datenschutz": {
        "hosting": "[Contabo GmbH, München]",
        "kontakt_datenschutz": "[deine@email.de]",
        "aufbewahrung_logs": "30 Tage",
        "aufsichtsbehoerde": "[Landesbeauftragter für den Datenschutz und die Informationsfreiheit Baden-Württemberg]",
        "stand": "[24.10.2026]",
    },
}

FILLED = {
    "betreiber": {
        "name": "Test GmbH",
        "strasse": "Teststraße 1",
        "plz_ort": "12345 Teststadt",
        "land": "Deutschland",
        "email": "test@example.org",
        "telefon": "+49 123 456",
        "umsatzsteuer_id": "DE123456789",
        "verantwortlich": "Max Mustermann",
    },
    "datenschutz": {
        "hosting": "Testhosting GmbH, Teststadt",
        "kontakt_datenschutz": "datenschutz@example.org",
        "aufbewahrung_logs": "30 Tage",
        "aufsichtsbehoerde": "Test-Datenschutzbehörde",
        "stand": "23.10.2026",
    },
}


OPTIONAL_PLACEHOLDER = copy.deepcopy(FILLED)
OPTIONAL_PLACEHOLDER["betreiber"]["telefon"] = "[42313095876]"


def main() -> int:
    checks: list[tuple[bool, str]] = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        checks.append((bool(ok), label))
        print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))

    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "empty.yaml"
        empty.write_text(yaml.safe_dump({"betreiber": {}, "datenschutz": {}}), encoding="utf-8")
        filled = Path(tmp) / "filled.yaml"
        filled.write_text(yaml.safe_dump(FILLED, allow_unicode=True), encoding="utf-8")
        placeholders = Path(tmp) / "placeholders.yaml"
        placeholders.write_text(yaml.safe_dump(PLACEHOLDER, allow_unicode=True), encoding="utf-8")
        optional_placeholder = Path(tmp) / "optional_placeholder.yaml"
        optional_placeholder.write_text(yaml.safe_dump(OPTIONAL_PLACEHOLDER, allow_unicode=True), encoding="utf-8")

        # 1) Leer -> noindex
        with serve(empty, 8082) as base:
            for path in ("/impressum", "/datenschutz"):
                html = httpx.get(base + path, timeout=10).text
                check('content="noindex,follow"' in html, f"{path}: noindex bei leeren Feldern")
                check("Noch nicht konfiguriert" in html, f"{path}: Hinweis sichtbar")
                label = "Name / Firma" if path == "/impressum" else "Hosting-Anbieter"
                check(label in html, f"{path}: fehlende Pflichtfelder gelistet")
            sitemap = httpx.get(base + "/sitemap.xml", timeout=10).text
            check("/impressum" not in sitemap and "/datenschutz" not in sitemap,
                  "Sitemap: keine noindex-Rechtsseiten")

        # 2) Platzhalter -> weiterhin noindex
        with serve(placeholders, 8084) as base:
            imp = httpx.get(base + "/impressum", timeout=10).text
            ds = httpx.get(base + "/datenschutz", timeout=10).text
            check('content="noindex,follow"' in imp, "/impressum: noindex bei Platzhaltern")
            check('content="noindex,follow"' in ds, "/datenschutz: noindex bei Platzhaltern")
            check("Name / Firma" in imp, "/impressum: Platzhalter als fehlend gelistet")
            check("Hosting-Anbieter" in ds, "/datenschutz: Platzhalter als fehlend gelistet")
            check("Batnini" not in imp, "/impressum: keine Platzhalterdaten gerendert")
            sitemap = httpx.get(base + "/sitemap.xml", timeout=10).text
            check("/impressum" not in sitemap and "/datenschutz" not in sitemap,
                  "Sitemap: Platzhalter-Seiten nicht enthalten")

        # 3) Optionaler Platzhalter -> weiterhin noindex
        with serve(optional_placeholder, 8085) as base:
            imp = httpx.get(base + "/impressum", timeout=10).text
            check('content="noindex,follow"' in imp,
                  "/impressum: noindex bei optionalem Platzhalter")
            check("Telefon (Platzhalter)" in imp,
                  "/impressum: optionaler Platzhalter gelistet")

        # 4) Vollständig -> index
        with serve(filled, 8083) as base:
            imp = httpx.get(base + "/impressum", timeout=10).text
            ds = httpx.get(base + "/datenschutz", timeout=10).text
            check('content="index,follow"' in imp, "/impressum: indexierbar bei vollständigen Feldern")
            check("Test GmbH" in imp and "DE123456789" in imp and "Max Mustermann" in imp,
                  "/impressum: Pflichtangaben gerendert")
            check('content="index,follow"' in ds, "/datenschutz: indexierbar bei vollständigen Feldern")
            check("Testhosting GmbH" in ds and "Test-Datenschutzbehörde" in ds,
                  "/datenschutz: Hoster und Aufsichtsbehörde gerendert")
            check("x402-Zahlungen" in ds, "/datenschutz: x402/Blockchain-Hinweis vorhanden")
            sitemap = httpx.get(base + "/sitemap.xml", timeout=10).text
            check("/impressum" in sitemap and "/datenschutz" in sitemap,
                  "Sitemap: vollständige Rechtsseiten enthalten")

    passed = sum(1 for ok, _ in checks if ok)
    print(f"\nErgebnis: {passed}/{len(checks)} Prüfungen bestanden")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
