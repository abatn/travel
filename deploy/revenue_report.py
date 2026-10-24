#!/usr/bin/env python3
"""Weist den echten (fremden) USDC-Umsatz auf Base Mainnet aus.

Liest on-chain alle USDC-Transfers an unsere payTo-Adresse und zählt nur
Zahlungen von FREMDEN Wallets als Umsatz. Eigene Wallets (payTo selbst,
Testkäufer und optional OWN_WALLETS) werden ausgeschlossen.

Der Startblock des Zeitfensters wird standardmäßig aus der Blockzeit
geschätzt (~2 s pro Block bei Base). Das ist bewusst eine Schätzung und
keine exakte Zeitgrenze; für ein exaktes Fenster `--from-block N` nutzen.

Zusätzlich wird das Server-Ledger (attest/state/invoices.jsonl) informativ
gegen die On-chain-Zahlungen abgeglichen. Fehlt die Datei, läuft das Skript
normal weiter.

Umgebungsvariablen:
  BASE_RPC_URL  RPC-Endpunkt (Standard: https://base-rpc.publicnode.com)
  OWN_WALLETS   zusätzliche eigene Wallets, kommagetrennt

Aufruf:
  python3 deploy/revenue_report.py [--days 30] [--json] [--from-block N]
                                   [--out PFAD]

Es werden keine Mails verschickt. Die einzige optionale Schreibaktion ist
die JSON-Datei über `--out`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "attest" / "state" / "invoices.jsonl"

RPC = os.getenv("BASE_RPC_URL", "https://base-rpc.publicnode.com")
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
PAYTO = "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4"
TEST_BUYER = "0xbD9345754b1b712b4db7aa43dB9189A339599d59"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

USDC_DECIMALS = 6
USDC_SCALE = 10 ** USDC_DECIMALS
BLOCK_SECONDS = 2.0  # Base: ca. 2 s pro Block
CHUNK = 5000  # bewährt aus deploy/payment_watch.py


# --------------------------------------------------------------------------
# Blockchain-Zugriff
# --------------------------------------------------------------------------
def rpc(method: str, params: list):
    """JSON-RPC-Aufruf mit User-Agent, Retry bei 429/5xx und Drosselung."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last_exc: Exception | None = None
    for attempt in range(6):
        req = urllib.request.Request(RPC, data=body, headers={
            "Content-Type": "application/json",
            "User-Agent": "reise-agent-revenue-report/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                last_exc = exc
                time.sleep(min(2 ** attempt, 30))
                continue
            raise
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt < 5:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise
        if "error" in data:
            raise RuntimeError(f"RPC-Fehler: {data['error']}")
        time.sleep(0.5)
        return data["result"]
    raise RuntimeError(f"RPC nach mehreren Versuchen fehlgeschlagen: {last_exc}")


def get_block_number() -> int:
    """Aktuelle Blockhöhe (head) von Base."""
    return int(rpc("eth_blockNumber", []), 16)


def block_timestamp(block: int) -> int | None:
    """Unix-Zeitstempel eines Blocks; None, wenn er nicht ermittelbar ist."""
    try:
        data = rpc("eth_getBlockByNumber", [hex(block), False])
    except Exception:  # noqa: BLE001 - Datum ist nur Komfort, kein Abbruchgrund
        return None
    if not data or "timestamp" not in data:
        return None
    try:
        return int(data["timestamp"], 16)
    except (TypeError, ValueError):
        return None


def pad_topic(addr: str) -> str:
    """Adresse als 32-Byte-Indexed-Topic auffüllen."""
    return "0x" + "0" * 24 + addr.lower()[2:]


def transfer_from_log(log: dict) -> dict | None:
    """ERC-20-Transfer-Log in ein einfaches Transfer-Dict umwandeln."""
    if log.get("removed"):
        return None
    topics = log.get("topics") or []
    if len(topics) < 3:
        return None
    try:
        amount_micro = int(log.get("data") or "0x0", 16)
        block = int(log["blockNumber"], 16)
        log_index = int(log.get("logIndex") or "0x0", 16)
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "payer": "0x" + str(topics[1])[-40:].lower(),
        "amount_micro": amount_micro,
        "block": block,
        "log_index": log_index,
        "tx_hash": str(log.get("transactionHash") or "").lower(),
    }


def find_transfers(start: int, end: int, progress=None) -> list[dict]:
    """Alle USDC-Transfers an PAYTO im Blockbereich [start, end] laden."""
    if start > end:
        return []
    transfers: list[dict] = []
    chunks = (end - start) // CHUNK + 1
    for number, lo in enumerate(range(start, end + 1, CHUNK), 1):
        hi = min(lo + CHUNK - 1, end)
        logs = rpc("eth_getLogs", [{
            "address": USDC,
            "fromBlock": hex(lo),
            "toBlock": hex(hi),
            "topics": [TRANSFER_TOPIC, None, pad_topic(PAYTO)],
        }])
        for log in logs:
            transfer = transfer_from_log(log)
            if transfer is not None:
                transfers.append(transfer)
        if progress is not None:
            progress(number, chunks, hi)
    transfers.sort(key=lambda t: (t["block"], t["log_index"]))
    return transfers


def _progress(done: int, total: int, block: int) -> None:
    if total > 20 and (done == total or done % 20 == 0):
        print(f"  ... Block {block} ({done}/{total} Abschnitte)", file=sys.stderr)


# --------------------------------------------------------------------------
# Reine Auswertungsfunktionen (testbar ohne Netzwerk)
# --------------------------------------------------------------------------
def own_wallets() -> set[str]:
    """Eigene Wallets (klein geschrieben), inkl. optionaler OWN_WALLETS."""
    wallets = {PAYTO.lower(), TEST_BUYER.lower()}
    for item in os.getenv("OWN_WALLETS", "").split(","):
        item = item.strip().lower()
        if item:
            wallets.add(item)
    return wallets


def estimate_from_block(head: int, days: float,
                        block_seconds: float = BLOCK_SECONDS) -> int:
    """Startblock für `days` Tage schätzen (untere Grenze, >= 0).

    Base produziert ca. alle 2 s einen Block. Die Schätzung ist bewusst
    konservativ: Sie kann je nach Netzlast einige Blöcke danebenliegen.
    Für exakte Zeitfenster ist `--from-block` zu verwenden.
    """
    if days <= 0:
        raise ValueError("days muss > 0 sein")
    if head < 0:
        raise ValueError("head darf nicht negativ sein")
    if block_seconds <= 0:
        raise ValueError("block_seconds muss > 0 sein")
    blocks = int(round(float(days) * 86400 / block_seconds))
    return max(0, head - blocks)


def _amount_micro(transfer: dict) -> int:
    """Betrag eines Transfers in Mikro-USDC (ganzzahlig, exakt)."""
    if transfer.get("amount_micro") is not None:
        return int(transfer["amount_micro"])
    return int(round(float(transfer.get("amount", 0)) * USDC_SCALE))


def _sort_key(transfer: dict) -> tuple[int, int]:
    return (int(transfer.get("block", 0)), int(transfer.get("log_index", 0)))


def _payment(transfer: dict) -> dict:
    """Kompakte Zahlungsdarstellung für erste/letzte/größte Zahlung."""
    payment = {
        "amount_usdc": round(_amount_micro(transfer) / USDC_SCALE, USDC_DECIMALS),
        "payer": str(transfer.get("payer", "")).lower(),
        "tx_hash": transfer.get("tx_hash") or "",
        "block": int(transfer.get("block", 0)),
    }
    if transfer.get("timestamp") is not None:
        payment["timestamp"] = int(transfer["timestamp"])
    return payment


def summarize(transfers: list[dict], own_wallets: set[str]) -> dict:
    """Transfers in Umsatz-Kennzahlen überführen (nur fremde Wallets zählen)."""
    own = {str(wallet).lower() for wallet in own_wallets}
    external: list[dict] = []
    own_count = 0

    for transfer in transfers:
        if str(transfer.get("payer", "")).lower() in own:
            own_count += 1
        else:
            external.append(transfer)

    external_micro = sum(_amount_micro(t) for t in external)
    own_micro = sum(_amount_micro(t) for t in transfers if str(t.get("payer", "")).lower() in own)
    payers = sorted({str(t.get("payer", "")).lower() for t in external if t.get("payer")})

    largest = max(external, key=_amount_micro) if external else None
    first = min(external, key=_sort_key) if external else None
    last = max(external, key=_sort_key) if external else None

    return {
        "transfers_total": len(transfers),
        "transfers_external": len(external),
        "transfers_own": own_count,
        "external_volume_usdc": round(external_micro / USDC_SCALE, USDC_DECIMALS),
        "external_volume_micro": external_micro,
        "own_volume_usdc": round(own_micro / USDC_SCALE, USDC_DECIMALS),
        "own_volume_micro": own_micro,
        "unique_payers": len(payers),
        "payer_addresses": payers,
        "largest_payment": _payment(largest) if largest else None,
        "first_payment": _payment(first) if first else None,
        "last_payment": _payment(last) if last else None,
    }


def add_payment_times(summary: dict, head: int, head_ts: int | None,
                      actual: dict[int, int]) -> None:
    """Echte Blockzeiten ergänzen; sonst aus head und ~2 s/Block schätzen."""
    for key in ("largest_payment", "first_payment", "last_payment"):
        payment = summary.get(key)
        if not payment:
            continue
        block = int(payment["block"])
        if block in actual:
            payment["timestamp"] = actual[block]
            payment["time_estimated"] = False
        elif head_ts is not None:
            payment["timestamp"] = head_ts - int((head - block) * BLOCK_SECONDS)
            payment["time_estimated"] = True


def parse_iso_ts(value: str | None) -> float | None:
    """ISO-8601-Zeitstempel (auch mit Z) in Unix-Zeit umwandeln."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def load_ledger(path: Path = LEDGER) -> list[dict]:
    """JSON-Lines-Ledger lesen; fehlende/kaputte Zeilen tolerieren."""
    path = Path(path)
    if not path.exists():
        return []
    invoices: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            invoices.append(item)
    return invoices


def reconcile_ledger(invoices: list[dict], transfers: list[dict],
                     own_wallets: set[str], cutoff_ts: float | None = None) -> dict:
    """Ledger-Rechnungen informativ mit den On-chain-Transfers abgleichen."""
    own = {str(wallet).lower() for wallet in own_wallets}
    onchain = {
        str(t.get("tx_hash", "")).lower(): t
        for t in transfers if t.get("tx_hash")
    }
    external_tx = {
        tx for tx, transfer in onchain.items()
        if str(transfer.get("payer", "")).lower() not in own
    }

    in_period: list[dict] = []
    for invoice in invoices:
        created = parse_iso_ts(invoice.get("created_at"))
        if cutoff_ts is not None and created is not None and created < cutoff_ts:
            continue
        in_period.append(invoice)

    external = [
        inv for inv in in_period
        if str(inv.get("payer", "")).lower() not in own
    ]
    matched = [
        inv for inv in in_period
        if str(inv.get("tx_hash", "")).lower() in onchain
    ]
    ledger_tx = {str(inv.get("tx_hash", "")).lower() for inv in in_period}
    ledger_tx.discard("")

    return {
        "ledger_present": True,
        "invoices_in_period": len(in_period),
        "invoices_external": len(external),
        "invoices_matched_onchain": len(matched),
        "invoices_without_onchain_tx": len(in_period) - len(matched),
        "onchain_external_without_invoice": len(external_tx - ledger_tx),
    }


# --------------------------------------------------------------------------
# Darstellung
# --------------------------------------------------------------------------
def _fmt_ts(ts: int | float | None, estimated: bool = False) -> str:
    if ts is None:
        return "unbekannt"
    text = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return text + (" (geschätzt)" if estimated else "")


def _fmt_payment(payment: dict | None, label: str) -> str:
    if not payment:
        return f"{label}: keine"
    parts = [f"{payment['amount_usdc']:.6f} USDC", f"von {payment['payer']}"]
    if payment.get("timestamp") is not None:
        parts.append("am " + _fmt_ts(payment["timestamp"],
                                     bool(payment.get("time_estimated"))))
    parts.append(f"Block {payment['block']}")
    if payment.get("tx_hash"):
        parts.append(f"Tx {payment['tx_hash']}")
    return f"{label}: " + ", ".join(parts)


def format_report(report: dict) -> str:
    """Menschenlesbaren deutschen Bericht erzeugen."""
    window = report["window"]
    summary = report["summary"]
    ledger = report.get("ledger") or {}
    lines: list[str] = []

    lines.append("Umsatzbericht: Reise-Agent Preis-Attestierungen (Base Mainnet, USDC)")
    lines.append("=" * 72)
    lines.append(f"Empfänger (payTo): {report['pay_to']}")
    lines.append(f"Zeitraum:     {_fmt_ts(window.get('from_time'))} bis "
                 f"{_fmt_ts(window.get('to_time'))}")
    lines.append(f"Blöcke:       {window['from_block']} bis {window['to_block']} (head)")
    if window.get("from_block_estimated"):
        days_label = "1 Tag" if window["days"] == 1 else f"{window['days']} Tage"
        lines.append(
            f"Startblock:   geschätzt aus ~{window['block_seconds']:.0f} s/Block "
            f"({days_label}) - Schätzung, keine exakte Zeitgrenze"
        )
        lines.append("              Für ein exaktes Fenster: --from-block N")
    else:
        lines.append("Startblock:   manuell per --from-block gesetzt")

    lines.append("")
    lines.append(f"Transfers:    {summary['transfers_total']} gesamt, davon "
                 f"{summary['transfers_external']} fremd und "
                 f"{summary['transfers_own']} eigene (nicht Umsatz)")
    lines.append(f"Fremder Umsatz: {summary['external_volume_usdc']:.6f} USDC")
    lines.append(f"Fremde Zahler:  {summary['unique_payers']} eindeutige Adresse(n)")
    if summary["payer_addresses"]:
        for payer in summary["payer_addresses"]:
            lines.append(f"  - {payer}")
    else:
        lines.append("  (keine)")

    lines.append(_fmt_payment(summary.get("largest_payment"), "Größte Einzelzahlung"))
    lines.append(_fmt_payment(summary.get("first_payment"), "Erste Zahlung"))
    lines.append(_fmt_payment(summary.get("last_payment"), "Letzte Zahlung"))

    if summary["transfers_own"]:
        lines.append(f"Eigene Zahlungen: {summary['transfers_own']} (nicht Umsatz, "
                     f"Summe {summary['own_volume_usdc']:.6f} USDC)")
    else:
        lines.append("Eigene Zahlungen: 0 (nicht Umsatz)")

    lines.append("")
    if not ledger.get("ledger_present"):
        lines.append("Ledger-Abgleich: invoices.jsonl nicht vorhanden (übersprungen)")
    else:
        lines.append("Ledger-Abgleich (informativ, attest/state/invoices.jsonl):")
        rows = [
            ("Rechnungen im Zeitraum:",
             f"{ledger['invoices_in_period']} (davon fremd: {ledger['invoices_external']})"),
            ("Mit On-chain-Tx verknüpft:", str(ledger["invoices_matched_onchain"])),
            ("Rechnungen ohne On-chain-Tx:", str(ledger["invoices_without_onchain_tx"])),
            ("Fremde On-chain-Zahlungen ohne Rechnung:",
             str(ledger["onchain_external_without_invoice"])),
        ]
        width = max(len(label) for label, _ in rows)
        for label, value in rows:
            lines.append(f"  {label:<{width}} {value}")

    lines.append("")
    lines.append("Nur fremde Wallets zählen als Umsatz.")
    lines.append(f"Stand: {report['generated_at']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("muss eine ganze Zahl sein") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("muss > 0 sein")
    return number


def _non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("muss eine ganze Zahl sein") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("darf nicht negativ sein")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Weist den echten (fremden) USDC-Umsatz auf Base Mainnet aus.",
    )
    parser.add_argument("--days", type=_positive_int, default=30,
                        help="Zeitfenster in Tagen (Standard: 30)")
    parser.add_argument("--from-block", type=_non_negative_int, default=None,
                        help="Startblock exakt setzen (überschreibt --days)")
    parser.add_argument("--json", action="store_true",
                        help="Ergebnis maschinenlesbar als JSON ausgeben")
    parser.add_argument("--out", type=Path, default=None,
                        help="Ergebnis zusätzlich als JSON-Datei schreiben")
    return parser


def build_report(args: argparse.Namespace) -> dict:
    """On-chain-Daten laden und vollständigen Bericht zusammenbauen."""
    head = get_block_number()
    if args.from_block is not None:
        start = args.from_block
        if start > head:
            raise ValueError(f"--from-block {start} liegt über dem aktuellen Block {head}")
        estimated = False
    else:
        start = estimate_from_block(head, args.days)
        estimated = True

    own = own_wallets()
    transfers = find_transfers(start, head, progress=_progress)
    summary = summarize(transfers, own)

    head_ts = block_timestamp(head)
    start_ts = block_timestamp(start) if start != head else head_ts
    if start_ts is None and head_ts is not None:
        start_ts = head_ts - int((head - start) * BLOCK_SECONDS)

    actual_times: dict[int, int] = {}
    blocks = {
        int(p["block"])
        for key in ("largest_payment", "first_payment", "last_payment")
        if (p := summary.get(key))
    }
    for block in sorted(blocks):
        ts = block_timestamp(block)
        if ts is not None:
            actual_times[block] = ts
    add_payment_times(summary, head, head_ts, actual_times)

    invoices = load_ledger()
    if LEDGER.exists():
        ledger = reconcile_ledger(invoices, transfers, own, cutoff_ts=start_ts)
    else:
        ledger = {"ledger_present": False}

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "generated_at": generated,
        "network": "eip155:8453 (Base Mainnet)",
        "token": {"symbol": "USDC", "contract": USDC, "decimals": USDC_DECIMALS},
        "pay_to": PAYTO,
        "own_wallets": sorted(own),
        "window": {
            "days": args.days,
            "from_block": start,
            "to_block": head,
            "head_block": head,
            "from_block_estimated": estimated,
            "block_seconds": BLOCK_SECONDS,
            "from_time": int(start_ts) if start_ts is not None else None,
            "to_time": int(head_ts) if head_ts is not None else None,
        },
        "summary": summary,
        "ledger": ledger,
        "note": "Nur fremde Wallets zählen als Umsatz.",
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_report(args)
    except Exception as exc:  # noqa: BLE001 - CLI mit klarer Fehlermeldung
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json:
        print(payload)
    else:
        print(format_report(report))

    if args.out is not None:
        try:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Fehler beim Schreiben von {args.out}: {exc}", file=sys.stderr)
            return 1
        print(f"JSON geschrieben: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
