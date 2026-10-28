#!/usr/bin/env python3
"""Prüft llms.txt, erweiterte agent-payments.json und /api/register."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
MOCK_PORT = 8099
APP_PORT = 8078
BASE = f"http://127.0.0.1:{APP_PORT}"


def _free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _wait(url: str, timeout: float = 40) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    raise RuntimeError(f"{url} nicht erreichbar")


def main() -> int:
    for port in (MOCK_PORT, APP_PORT):
        if not _free(port):
            print(f"Port {port} belegt – Test nicht gestartet.")
            return 1

    tmp = Path(tempfile.mkdtemp(prefix="attest-discovery-"))
    config = tmp / "config.yaml"
    config.write_text(yaml.safe_dump({
        "enabled": True,
        "issuer": {"did": "did:web:test", "key_file": str(tmp / "issuer.key"),
                   "ttl_seconds": 300},
        "payment": {
            "price": "$0.002",
            "network": "eip155:84532",
            "pay_to": "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4",
            "max_timeout_seconds": 120,
            "facilitator": {"url": f"http://127.0.0.1:{MOCK_PORT}", "timeout": 10,
                            "auth": {"mode": "none"}},
        },
    }, allow_unicode=True), encoding="utf-8")

    env = dict(os.environ)
    env.update({
        "ATTEST_CONFIG": str(config),
        "ATTEST_PUBLIC_BASE_URL": BASE,
        "PYTHONPATH": str(ROOT),
    })

    procs: list[subprocess.Popen] = []
    try:
        mock = subprocess.Popen(
            [PY, "-m", "uvicorn", "attest.tests.mock_facilitator:app",
             "--host", "127.0.0.1", "--port", str(MOCK_PORT), "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(mock)
        _wait(f"http://127.0.0.1:{MOCK_PORT}/supported")

        app = subprocess.Popen(
            [PY, "-m", "uvicorn", "ui.app:app", "--host", "127.0.0.1",
             "--port", str(APP_PORT), "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(app)
        _wait(f"{BASE}/health")

        checks: list[tuple[bool, str]] = []

        def check(ok: bool, label: str, detail: str = "") -> None:
            checks.append((bool(ok), label))
            print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))

        # llms.txt
        llms = httpx.get(f"{BASE}/llms.txt", timeout=10)
        check(llms.status_code == 200, "GET /llms.txt -> 200", str(llms.status_code))
        check("text/plain" in llms.headers.get("content-type", ""), "llms.txt: text/plain")
        check("{{" not in llms.text, "llms.txt: alle Platzhalter ersetzt")
        check(f"{BASE}/api/attest" in llms.text, "llms.txt: Endpoint absolut")
        check("0.002 USDC" in llms.text, "llms.txt: Preis genannt")
        check("eip155:84532" in llms.text, "llms.txt: Netz genannt")

        # agent-payments.json
        disc = httpx.get(f"{BASE}/.well-known/agent-payments.json", timeout=10)
        check(disc.status_code == 200, "agent-payments.json -> 200", str(disc.status_code))
        data = disc.json()
        check(data.get("version") == "1", "Discovery: version")
        check(bool(data.get("provider", {}).get("contact", {}).get("url")),
              "Discovery: provider.contact.url")
        check(data.get("documentation", "").endswith("/llms.txt"),
              "Discovery: documentation -> llms.txt")
        resources = data.get("resources") or []
        check(len(resources) == 1, "Discovery: eine Ressource", str(len(resources)))
        res = resources[0]
        check(res.get("type") == "http" and res.get("x402Version") == 2,
              "Discovery: type/x402Version")
        check(res.get("resource", "").endswith("/api/attest"), "Discovery: resource URL")
        acc = (res.get("accepts") or [{}])[0]
        check(acc.get("scheme") == "exact", "Discovery: scheme exact")
        check(acc.get("network") == "eip155:84532", "Discovery: network", acc.get("network"))
        check(acc.get("amount") == "2000", "Discovery: amount 2000 atomic", acc.get("amount"))
        check(acc.get("payTo", "").lower() == "0x1ce5379a485a0bd726fce57bbfdfc316b0d35cc4",
              "Discovery: payTo")
        check(bool(acc.get("asset")), "Discovery: asset")
        bazaar = (res.get("extensions") or {}).get("bazaar") or {}
        check(bool(bazaar.get("info")), "Discovery: bazaar.info")
        check(bool(bazaar.get("schema")), "Discovery: bazaar.schema")
        check((bazaar.get("info", {}).get("input", {}).get("method") == "POST"),
              "Discovery: bazaar input POST")

        # x402-Manifest für Saylor Agent Bazaar
        man = httpx.get(f"{BASE}/.well-known/x402.json", timeout=10)
        check(man.status_code == 200, "x402.json -> 200", str(man.status_code))
        manifest = man.json()
        check(manifest.get("x402Version") == 2, "x402.json: x402Version 2")
        mres = (manifest.get("resources") or [{}])[0]
        check(str(mres.get("url", "")).endswith("/api/attest"), "x402.json: resource URL")
        check(bool(mres.get("accepts")), "x402.json: accepts[]")
        check(bool((mres.get("outputSchema") or {}).get("required")),
              "x402.json: outputSchema")
        check("travel" in (mres.get("tags") or []), "x402.json: tags")
        check("manifest" in (data.get("endpoints") or {}),
              "Discovery: manifest-Endpunkt verlinkt")

        # Verzeichnis-Probing: CDP /v2/x402/validate, PayAI und gold-402 prüfen
        # per HEAD/GET auf 402. Ohne 402 für diese Methoden wird die Ressource
        # nicht katalogisiert (returns_402 failed -> resource abgelehnt).
        import base64 as _b64

        for method in ("GET", "HEAD"):
            probe = httpx.request(method, f"{BASE}/api/attest", timeout=10)
            check(probe.status_code == 402,
                  f"Probe: {method} /api/attest -> 402", str(probe.status_code))
            challenge = probe.headers.get("payment-required", "")
            try:
                decoded = json.loads(_b64.b64decode(challenge + "=" * (-len(challenge) % 4)))
            except Exception:  # noqa: BLE001
                decoded = {}
            check(str(decoded.get("resource", {}).get("url", "")).endswith("/api/attest"),
                  f"Probe: {method} nennt resource")
            check(bool((decoded.get("extensions") or {}).get("bazaar")),
                  f"Probe: {method} enthält bazaar-Extension")
            check(bool(decoded.get("accepts")), f"Probe: {method} enthält accepts")

        # Browser-Request (Paywall-HTML) darf keine 500 auslösen
        browser = httpx.get(
            f"{BASE}/api/attest",
            headers={"Accept": "text/html,application/xhtml+xml",
                     "User-Agent": "Mozilla/5.0 (directory-check)"},
            timeout=10,
        )
        check(browser.status_code == 402, "Browser-GET /api/attest -> 402",
              str(browser.status_code))
        check("text/html" in browser.headers.get("content-type", ""),
              "Browser-GET: Paywall-HTML", browser.headers.get("content-type", ""))

        # unbezahlter POST bleibt 402 (unverändert)
        post_probe = httpx.post(f"{BASE}/api/attest", json={}, timeout=10)
        check(post_probe.status_code == 402, "Probe: POST /api/attest -> 402",
              str(post_probe.status_code))

        # register
        reg = httpx.post(f"{BASE}/api/register", timeout=10)
        check(reg.status_code == 200, "POST /api/register -> 200", str(reg.status_code))
        body = reg.json()
        check(body.get("status") == "simulated", "Register: status simulated")
        check(len(body.get("manual_steps") or []) >= 4, "Register: manuelle Schritte")
        check(body.get("payload", {}).get("resource", {}).get("resource", "").endswith("/api/attest"),
              "Register: Payload enthält Ressource")
        check(Path(body.get("saved_to", "")).exists(), "Register: Payload gespeichert")

        passed = sum(1 for ok, _ in checks if ok)
        print(f"\nErgebnis: {passed}/{len(checks)} Prüfungen bestanden")
        return 0 if passed == len(checks) else 1
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
