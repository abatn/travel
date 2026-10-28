#!/usr/bin/env python3
"""Beweist die PayAPI-Anforderungen der zweiten M2-Instanz.

Startet Mock-Facilitator + App, prüft:
  * unbezahlt: GET/HEAD/POST -> 402, keine Produktdaten
  * Challenge: Base, USDC, 0.01 USDC, payTo, extra.name="USD Coin"
  * bezahlt: GET/POST -> 200 + echte signierte Attestierung
  * eigene Discovery /.well-known/x402
  * eigener Schlüssel, eigener Ledger, eigene Instanz
"""
from __future__ import annotations

import asyncio
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

ROOT = Path(__file__).resolve().parents[3]
MOCK_PORT = 8097
APP_PORT = 8098
BASE = f"http://127.0.0.1:{APP_PORT}"
PAY_TO = "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4"
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def _free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _wait(url: str, timeout: float = 45) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    raise RuntimeError(f"{url} nicht erreichbar")


def _decode(response: httpx.Response) -> dict:
    header = response.headers.get("payment-required", "")
    if header:
        import base64

        try:
            return json.loads(base64.b64decode(header + "=" * (-len(header) % 4)))
        except Exception:  # noqa: BLE001
            pass
    try:
        return response.json()
    except Exception:  # noqa: BLE001
        return {}


class PaidClient:
    def __init__(self, key: str):
        from eth_account import Account
        from x402 import x402Client
        from x402.http.clients.httpx import x402AsyncTransport
        from x402.mechanisms.evm.exact.client import ExactEvmScheme
        from x402.mechanisms.evm.signers import EthAccountSigner

        self.account = Account.from_key(key)
        client = x402Client()
        client.register("eip155:8453", ExactEvmScheme(EthAccountSigner(self.account)))
        self.transport = x402AsyncTransport(client)

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(transport=self.transport, timeout=60) as http:
            return await http.request(method, url, **kwargs)


def main() -> int:
    for port in (MOCK_PORT, APP_PORT):
        if not _free(port):
            print(f"Port {port} belegt – Test nicht gestartet.")
            return 1

    tmp = Path(tempfile.mkdtemp(prefix="payapi-test-"))
    payapi_config = tmp / "payapi.yaml"
    payapi_config.write_text(yaml.safe_dump({
        "enabled": True,
        "instance": "payapi-test",
        "public_base_url": BASE,
        "ledger": str(tmp / "invoices.jsonl"),
        "issuer": {
            "did": "did:web:test:payapi",
            "key_file": str(tmp / "issuer.ed25519"),
            "ttl_seconds": 300,
        },
        "payment": {
            "price": "$0.01",
            "network": "eip155:8453",
            "asset": ASSET,
            "pay_to": PAY_TO,
            "max_timeout_seconds": 120,
            "extra": {"name": "USD Coin", "version": "2"},
            "facilitator": {
                "url": f"http://127.0.0.1:{MOCK_PORT}",
                "timeout": 10,
                "auth": {"mode": "none"},
            },
        },
    }, allow_unicode=True), encoding="utf-8")

    # Hauptinstanz für diesen Test deaktivieren, damit nur PayAPI geprüft wird.
    main_config = tmp / "main.yaml"
    main_config.write_text("enabled: false\n", encoding="utf-8")

    env = dict(os.environ)
    env.update({
        "PAYAPI_CONFIG": str(payapi_config),
        "ATTEST_CONFIG": str(main_config),
        "MOCK_NETWORK": "eip155:8453",
        "PYTHONPATH": str(ROOT),
    })

    procs: list[subprocess.Popen] = []
    checks: list[tuple[bool, str]] = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        checks.append((bool(ok), label))
        print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))

    try:
        procs.append(subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "attest.tests.mock_facilitator:app",
             "--host", "127.0.0.1", "--port", str(MOCK_PORT), "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        _wait(f"http://127.0.0.1:{MOCK_PORT}/supported")

        procs.append(subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "ui.app:app", "--host", "127.0.0.1",
             "--port", str(APP_PORT), "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        _wait(f"{BASE}/health")

        # --- Discovery ---
        man = httpx.get(f"{BASE}/.well-known/x402", timeout=10)
        check(man.status_code == 200, "Discovery /.well-known/x402 -> 200", str(man.status_code))
        m = man.json()
        check(m.get("x402Version") == 2, "Discovery: x402Version 2")
        r = (m.get("resources") or [{}])[0]
        check(str(r.get("url", "")).endswith("/api/attest-v2"), "Discovery: URL /api/attest-v2")
        a = (r.get("accepts") or [{}])[0]
        check(a.get("network") == "eip155:8453", "Discovery: Base-Mainnet", a.get("network"))
        check(a.get("asset") == ASSET, "Discovery: kanonisches USDC", a.get("asset"))
        check(a.get("amount") == "10000", "Discovery: 0.01 USDC (10000)", a.get("amount"))
        check(a.get("payTo", "").lower() == PAY_TO.lower(), "Discovery: payTo")
        check((a.get("extra") or {}).get("name") == "USD Coin", "Discovery: extra.name=USD Coin")
        check(bool(r.get("outputSchema")), "Discovery: outputSchema")

        # --- unbezahlt ---
        last_required: dict = {}
        for method in ("GET", "HEAD", "POST"):
            resp = httpx.request(method, f"{BASE}/api/attest-v2", json={} if method == "POST" else None,
                                 timeout=20)
            check(resp.status_code == 402, f"unbezahlt {method} -> 402", str(resp.status_code))
            required = _decode(resp)
            last_required = required
            acc = (required.get("accepts") or [{}])[0]
            check(acc.get("amount") == "10000", f"unbezahlt {method}: amount 10000", acc.get("amount"))
            check((acc.get("extra") or {}).get("name") == "USD Coin",
                  f"unbezahlt {method}: extra.name", (acc.get("extra") or {}).get("name"))
            check("signature" not in resp.text and '"id"' not in resp.text,
                  f"unbezahlt {method}: keine Produktdaten")

        # --- Bazaar-Erweiterung (CDP x402 Bazaar) ---
        bazaar = (last_required.get("extensions") or {}).get("bazaar") or {}
        info = bazaar.get("info") or {}
        inp = info.get("input") or {}
        out = info.get("output") or {}
        check(bool(bazaar), "402: extensions.bazaar vorhanden")
        check(inp.get("type") == "http" and inp.get("method") == "POST",
              "Bazaar: input type=http/method=POST", f"{inp.get('type')}/{inp.get('method')}")
        check((inp.get("body") or {}).get("route") == "BER-FCO",
              "Bazaar: input.body.route Beispiel", (inp.get("body") or {}).get("route"))
        check(isinstance(out.get("example"), dict) and bool(out.get("example")),
              "Bazaar: output.example vorhanden")
        check(bool(bazaar.get("schema")), "Bazaar: schema vorhanden")

        # Browser-Request darf keine 500 auslösen (Paywall-HTML)
        browser = httpx.get(
            f"{BASE}/api/attest-v2",
            headers={"Accept": "text/html,application/xhtml+xml",
                     "User-Agent": "Mozilla/5.0 (PayAPI-Check)"},
            timeout=20,
        )
        check(browser.status_code == 402, "Browser-GET -> 402 statt 500",
              str(browser.status_code))
        check("text/html" in browser.headers.get("content-type", ""),
              "Browser-GET: Paywall-HTML", browser.headers.get("content-type", ""))

        # --- bezahlt (echter x402-Client, Mock-Facilitator) ---
        from eth_account import Account

        account = Account.create()
        paid = PaidClient(account.key.hex())

        async def flow() -> None:
            # GET mit Query -> echte Beobachtung
            get_resp = await paid.request(
                "GET", f"{BASE}/api/attest-v2",
                params={"route": "HAM-FCO", "travel_date": "2026-11-05",
                        "price": "199.99", "source": "payapi-test"})
            check(get_resp.status_code == 200, "bezahlt GET -> 200", str(get_resp.status_code))
            doc = get_resp.json()
            check(doc.get("subject", {}).get("route") == "HAM-FCO", "GET: Route übernommen")
            check(bool(doc.get("signature", {}).get("value")), "GET: Signatur vorhanden")
            check(doc.get("instance") == "payapi-test", "GET: eigene Instanz")

            ver = httpx.post(f"{BASE}/api/attest-v2/verify", json={"document": doc}, timeout=10)
            check(ver.status_code == 200 and ver.json().get("valid") is True,
                  "GET: Signatur verifiziert", str(ver.json())[:80])

            # POST mit Body
            post_resp = await paid.request(
                "POST", f"{BASE}/api/attest-v2",
                json={"route": "BER-FCO", "travel_date": "2026-11-05",
                      "price": "129.99", "currency": "EUR",
                      "price_scope": "per_person", "source": "payapi-test",
                      "source_url": "https://payapi.market", "passengers": 1})
            check(post_resp.status_code == 200, "bezahlt POST -> 200", str(post_resp.status_code))
            post_doc = post_resp.json()
            check(post_doc.get("subject", {}).get("source") == "payapi-test", "POST: Quelle übernommen")
            check(bool(post_doc.get("signature", {}).get("value")), "POST: Signatur vorhanden")

            # POST leer -> Referenz (Canary-Robustheit)
            ref_resp = await paid.request("POST", f"{BASE}/api/attest-v2", json={})
            check(ref_resp.status_code == 200, "bezahlt POST leer -> 200", str(ref_resp.status_code))
            ref = ref_resp.json()
            check(ref.get("subject", {}).get("source") == "payapi-reference",
                  "leerer POST: Referenz-Attestierung")

        asyncio.run(flow())

        # --- eigener Ledger ---
        ledger = tmp / "invoices.jsonl"
        check(ledger.exists(), "eigener Ledger existiert")
        if ledger.exists():
            rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x]
            check(len(rows) >= 3, "eigener Ledger: Rechnungen geschrieben", str(len(rows)))
            check(all(r.get("service", "").endswith("(PayAPI)") for r in rows),
                  "eigener Ledger: PayAPI-Leistung")

        key_file = tmp / "issuer.ed25519"
        main_key = (ROOT / "attest" / "keys" / "issuer.ed25519").resolve()
        check(key_file.exists(), "eigener Ed25519-Schlüssel existiert")
        check(key_file.resolve() != main_key, "Schlüssel ist nicht der Hauptschlüssel")

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
