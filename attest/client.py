#!/usr/bin/env python3
"""Test-Client für /api/attest (x402).

Beispiele:
    # 1) Nur prüfen, was der Server verlangt (kein Schlüssel nötig)
    .venv-x402/bin/python -m attest.client --probe

    # 2) Wallet erzeugen (Adresse ausgeben, dann testnet-USDC besorgen)
    .venv-x402/bin/python -m attest.client --generate-key

    # 3) Bezahlen und Attestierung abrufen
    X402_TEST_PRIVATE_KEY=0x... .venv-x402/bin/python -m attest.client
    .venv-x402/bin/python -m attest.client --key-file attest/keys/buyer.key
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE = "http://127.0.0.1:8077"

SAMPLE = {
    "route": "BER-FCO",
    "travel_date": "2026-11-05",
    "price": "129.99",
    "currency": "EUR",
    "price_scope": "per_person",
    "source": "googleflights-local",
    "source_url": "https://www.google.com/travel/flights",
    "passengers": 1,
}


def _decode_required(response: httpx.Response) -> dict[str, Any] | None:
    header = response.headers.get("payment-required")
    if header:
        try:
            raw = base64.b64decode(header + "=" * (-len(header) % 4))
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            pass
    try:
        return response.json()
    except Exception:  # noqa: BLE001
        return None


def _load_key(args) -> str | None:
    if args.key_file:
        path = Path(args.key_file)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8").strip()
    return os.environ.get(args.key_env, "").strip() or None


def _generate_key(path: Path) -> str:
    from eth_account import Account

    account = Account.create()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(account.key.hex(), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    print(f"Wallet erzeugt: {account.address}")
    print(f"Private Key:    {path} (geheim halten)")
    print("Testnet-USDC (Base Sepolia) besorgen: https://faucet.circle.com")
    return account.address


async def run(args) -> int:
    url = f"{args.base.rstrip('/')}/api/attest"

    if args.generate_key:
        _generate_key(Path(args.key_file or "attest/keys/buyer.key"))
        return 0

    if args.probe:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.post(url, json=SAMPLE)
        print(f"HTTP {response.status_code}")
        required = _decode_required(response)
        print(json.dumps(required, indent=2, ensure_ascii=False)[:4000])
        return 0 if response.status_code == 402 else 1

    key = _load_key(args)
    if not key:
        print("Kein Schlüssel. Nutze --generate-key, --key-file oder "
              f"{args.key_env}.", file=sys.stderr)
        return 2

    from eth_account import Account
    from x402 import x402Client
    from x402.http.clients.httpx import x402AsyncTransport
    from x402.mechanisms.evm.exact.client import ExactEvmScheme
    from x402.mechanisms.evm.signers import EthAccountSigner

    account = Account.from_key(key)
    print(f"Payer: {account.address}")
    network = args.network

    client = x402Client()
    client.register(network, ExactEvmScheme(EthAccountSigner(account)))
    transport = x402AsyncTransport(client)

    async with httpx.AsyncClient(transport=transport, timeout=90) as http:
        response = await http.post(url, json=SAMPLE)

    print(f"HTTP {response.status_code}")
    if response.status_code != 200:
        required = _decode_required(response)
        print(json.dumps(required or {"body": response.text[:1000]},
                         indent=2, ensure_ascii=False)[:4000])
        settlement = response.headers.get("payment-response")
        if settlement:
            try:
                decoded = json.loads(base64.b64decode(
                    settlement + "=" * (-len(settlement) % 4)))
                print("Settlement-Fehler:", json.dumps(decoded, ensure_ascii=False))
            except Exception:  # noqa: BLE001
                print("payment-response:", settlement[:500])
        return 2

    document = response.json()
    if args.output:
        Path(args.output).write_text(
            json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Attestierung gespeichert: {args.output}")
    else:
        print(json.dumps(document, indent=2, ensure_ascii=False))

    # Signatur gegen den Verifikations-Endpunkt prüfen
    async with httpx.AsyncClient(timeout=30) as http:
        verify = await http.post(
            f"{args.base.rstrip('/')}/api/attest/verify",
            json={"document": document},
        )
    print(f"Signaturprüfung: HTTP {verify.status_code} {verify.text[:300]}")
    settlement = response.headers.get("payment-response")
    if settlement:
        try:
            decoded = json.loads(base64.b64decode(
                settlement + "=" * (-len(settlement) % 4)))
            print(f"Settlement: {json.dumps(decoded, ensure_ascii=False)}")
        except Exception:  # noqa: BLE001
            print(f"Settlement-Header: {settlement[:200]}")
    return 0 if verify.status_code == 200 else 3


def main() -> int:
    parser = argparse.ArgumentParser(description="x402-Testclient für /api/attest")
    parser.add_argument("--base", default=os.environ.get("ATTEST_BASE", DEFAULT_BASE))
    parser.add_argument("--network", default=os.environ.get("ATTEST_NETWORK", "eip155:84532"))
    parser.add_argument("--probe", action="store_true", help="nur 402-Antwort zeigen")
    parser.add_argument("--generate-key", action="store_true", help="neue Wallet erzeugen")
    parser.add_argument("--key-file", help="Datei mit Private Key (hex)")
    parser.add_argument("--key-env", default="X402_TEST_PRIVATE_KEY")
    parser.add_argument("--output", help="Attestierung als JSON speichern")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
