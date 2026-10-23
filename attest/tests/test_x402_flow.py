#!/usr/bin/env python3
"""End-to-End: 402 -> Zahlung -> Verify/Settle -> 200 -> Signatur -> Verify.

Startet einen wire-kompatiblen Test-Facilitator und die UI auf separaten Ports.
Damit ist der komplette Ablauf ohne Chain-Guthaben reproduzierbar; der echte
Facilitator ist nur eine andere URL in der Konfiguration.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

import yaml
from pathlib import Path

import httpx
from eth_account import Account
from x402 import x402Client
from x402.http.clients.httpx import x402AsyncTransport
from x402.mechanisms.evm.exact.client import ExactEvmScheme
from x402.mechanisms.evm.signers import EthAccountSigner

ROOT = Path(__file__).resolve().parents[2]
MOCK_PORT = 8099
APP_PORT = 8078
BASE = f"http://127.0.0.1:{APP_PORT}"
PAYLOAD = {
    "route": "BER-FCO",
    "travel_date": "2026-11-05",
    "price": "129.99",
    "currency": "EUR",
    "price_scope": "per_person",
    "source": "googleflights-local",
    "source_url": "https://www.google.com/travel/flights",
    "passengers": 1,
}


def _wait(url: str, timeout: float = 40) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.4)
    raise RuntimeError(f"{url} nicht erreichbar")


def _port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main() -> int:
    for port in (MOCK_PORT, APP_PORT):
        if not _port_free(port):
            print(f"Port {port} ist belegt – Test nicht gestartet.")
            return 1

    tmp = Path(tempfile.mkdtemp(prefix="attest-e2e-"))
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
    ledger = tmp / "invoices.jsonl"
    env = dict(os.environ)
    env.update({
        "ATTEST_CONFIG": str(config),
        "ATTEST_LEDGER": str(ledger),
        "ATTEST_PUBLIC_BASE_URL": BASE,
        "PYTHONPATH": str(ROOT),
    })

    procs: list[subprocess.Popen] = []
    try:
        mock = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "attest.tests.mock_facilitator:app",
             "--host", "127.0.0.1", "--port", str(MOCK_PORT), "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(mock)
        _wait(f"http://127.0.0.1:{MOCK_PORT}/supported")

        app = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "ui.app:app",
             "--host", "127.0.0.1", "--port", str(APP_PORT), "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(app)
        _wait(f"{BASE}/health")

        checks: list[tuple[bool, str]] = []

        def check(ok: bool, label: str, detail: str = "") -> None:
            checks.append((bool(ok), label))
            print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))

        # 1) Discovery
        discovery = httpx.get(f"{BASE}/.well-known/agent-payments.json", timeout=10).json()
        check(discovery["payment"]["network"] == "eip155:84532", "Discovery: Netz Base Sepolia",
              discovery["payment"]["network"])
        check(discovery["payment"]["pay_to"].lower()
              == "0x1ce5379a485a0bd726fce57bbfdfc316b0d35cc4",
              "Discovery: payTo korrekt")
        check(discovery["endpoints"]["attest"]["payment_required"] is True,
              "Discovery: /api/attest kostenpflichtig")

        # 2) 402
        response = httpx.post(f"{BASE}/api/attest", json=PAYLOAD, timeout=20)
        header = response.headers.get("payment-required", "")
        required = json.loads(base64.b64decode(header + "=" * (-len(header) % 4)))
        accept = required["accepts"][0]
        check(response.status_code == 402, "Ohne Zahlung: HTTP 402", str(response.status_code))
        check(accept["network"] == "eip155:84532", "402: Netz", accept["network"])
        check(accept["amount"] == "2000", "402: 0,002 USDC (2000 atomic)", accept["amount"])
        check(accept["asset"].lower() == "0x036cbd53842c5426634e7929541ec2318f3dcf7e",
              "402: USDC Base Sepolia")
        check(accept["payTo"].lower() == "0x1ce5379a485a0bd726fce57bbfdfc316b0d35cc4",
              "402: payTo")

        # 3) Bezahlen (Test-Wallet, Mock-Facilitator)
        account = Account.create()
        client = x402Client()
        client.register("eip155:84532", ExactEvmScheme(EthAccountSigner(account)))
        transport = x402AsyncTransport(client)

        async def pay():
            async with httpx.AsyncClient(transport=transport, timeout=60) as http:
                return await http.post(f"{BASE}/api/attest", json=PAYLOAD)

        paid = asyncio.run(pay())
        check(paid.status_code == 200, "Mit Zahlung: HTTP 200", str(paid.status_code))
        document = paid.json()
        check(bool(document.get("signature", {}).get("value")), "Attestierung signiert")
        check(document["subject"]["route"] == "BER-FCO", "Route im Dokument")
        check(document["subject"]["price"] == "129.99", "Preis als String")
        check(document["plausibility"]["status"] in ("ok", "warn"),
              "Plausibilität dokumentiert", document["plausibility"]["status"])

        settlement_header = paid.headers.get("payment-response", "")
        settlement = json.loads(
            base64.b64decode(settlement_header + "=" * (-len(settlement_header) % 4)))
        check(settlement.get("success") is True, "Settlement erfolgreich")
        import json as _json
        rows = [_json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        check(len(rows) == 1, "Rechnung geschrieben", str(len(rows)))
        if rows:
            check(rows[0].get("amount") == "0.002", "Rechnung: Betrag 0,002",
                  str(rows[0].get("amount")))
            check(rows[0].get("tx_hash") == settlement.get("transaction"),
                  "Rechnung: Tx-Hash übernommen")
        check(bool(settlement.get("transaction")), "Settlement-Transaktion vorhanden")

        # 4) Signatur fremd prüfen
        verify = httpx.post(f"{BASE}/api/attest/verify",
                            json={"document": document}, timeout=10).json()
        check(verify.get("valid") is True, "Signaturprüfung /api/attest/verify")

        # 5) Manipulation wird erkannt
        tampered = json.loads(json.dumps(document))
        tampered["subject"]["price"] = "1.00"
        bad = httpx.post(f"{BASE}/api/attest/verify",
                         json={"document": tampered}, timeout=10).json()
        check(bad.get("valid") is False, "Manipuliertes Dokument wird abgelehnt")

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
