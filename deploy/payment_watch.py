#!/usr/bin/env python3
"""Meldet per E-Mail jede Zahlung von FREMDEN Wallets an unsere payTo-Adresse.

Liest USDC-Transfers auf Base (eip155:8453) an PAYTO. Eigene Wallets
(OWN_WALLETS) werden ignoriert, damit Eigenzahlungen nicht als Umsatz gelten.
Eine Zahlung gilt erst als gemeldet, wenn die Mail erfolgreich ging; sonst
wird beim nächsten Lauf erneut versucht.

Umgebungsvariablen (aus /etc/reise-agent.env):
  SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD (App-Passwort)
  ALERT_TO (Standard: batniniabdelkader@yahoo.com)
Aufruf: python3 deploy/payment_watch.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "attest" / "state" / "payment_watch.json"
RPC = os.getenv("BASE_RPC_URL", "https://base-rpc.publicnode.com")
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
PAYTO = "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4"
OWN_WALLETS = {
    PAYTO.lower(),
    "0xbD9345754b1b712b4db7aa43dB9189A339599d59".lower(),  # Test-Käufer
}
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
LOOKBACK_BLOCKS = 40000  # ca. 1 Tag bei Base (~2 s pro Block)
CHUNK = 5000


def rpc(method: str, params: list):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for attempt in range(6):
        req = urllib.request.Request(RPC, data=body, headers={
            "Content-Type": "application/json",
            "User-Agent": "reise-agent-payment-watch/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 5:
                raise
            time.sleep(2 ** attempt)
            continue
        if "error" in data:
            raise RuntimeError(data["error"])
        time.sleep(0.5)
        return data["result"]


def pad_topic(addr: str) -> str:
    return "0x" + "0" * 24 + addr.lower()[2:]


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"last_block": None, "reported": []}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def find_transfers(start: int, end: int) -> list[dict]:
    found = []
    for lo in range(start, end + 1, CHUNK):
        hi = min(lo + CHUNK - 1, end)
        logs = rpc("eth_getLogs", [{
            "address": USDC,
            "fromBlock": hex(lo),
            "toBlock": hex(hi),
            "topics": [TRANSFER_TOPIC, None, pad_topic(PAYTO)],
        }])
        found.extend(logs)
    return found


def send_mail(subject: str, text: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"[dry-run] Mail: {subject}\n{text}")
        return True
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if not (host and user and password):
        print("SMTP nicht konfiguriert (SMTP_HOST/SMTP_USER/SMTP_PASSWORD fehlen) - keine Mail", file=sys.stderr)
        return False
    to = os.getenv("ALERT_TO", "batniniabdelkader@yahoo.com")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(text)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"Mailversand fehlgeschlagen: {exc}", file=sys.stderr)
        return False


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    state = load_state()
    head = int(rpc("eth_blockNumber", []), 16)
    start = state["last_block"] + 1 if state["last_block"] else head - LOOKBACK_BLOCKS
    reported = set(state["reported"])

    external = []
    for log in find_transfers(start, head):
        payer = "0x" + log["topics"][1][-40:]
        if payer.lower() in OWN_WALLETS:
            continue
        amount = int(log["data"], 16) / 1_000_000
        external.append((log["transactionHash"], payer, amount, int(log["blockNumber"], 16)))

    failed = 0
    for tx, payer, amount, block in external:
        if tx in reported:
            continue
        text = (
            "Neue Zahlung von einer FREMDEN Wallet an Reise-Agent Attest.\n\n"
            f"Betrag:   {amount:.6f} USDC\n"
            f"Zahler:   {payer}\n"
            f"Empfänger: {PAYTO} (Base)\n"
            f"Tx:       https://basescan.org/tx/{tx}\n"
            f"Block:    {block}\n"
        )
        if send_mail(f"Zahlung eingegangen: {amount:.2f} USDC", text, dry_run):
            reported.add(tx)
        else:
            failed += 1

    if not dry_run and failed == 0:
        state["last_block"] = head
    if not dry_run:
        state["reported"] = sorted(reported)
        save_state(state)
    print(f"Blöcke {start}-{head}: {len(external)} Fremdzahlung(en), neu gemeldet: {len([t for t in external if t[0] in reported])}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
