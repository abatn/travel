#!/usr/bin/env python3
"""TEST-STUB: simuliert eine Flug-API, die einen kaputten Preis liefert.

Der Stub bildet die Antwortform von `trvl` nach (`{"result": {"flights": [...]}}`),
damit der echte Runner unverändert darauf läuft. Er wird **nur** in Tests
verwendet und steht in keiner Live-Registry.

Aufruf:
    python3 fault_stub_server.py --port 8099 --price 0.01 [--real-price 27.99]
"""
from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

FLIGHTS = []


def flight(price: float, currency: str = "EUR", provider: str = "ryanair",
           flight_no: str = "FR134", dep: str = "2026-10-31T22:20",
           arr: str = "2026-11-01T00:30") -> dict:
    return {
        "price": price,
        "currency": currency,
        "all_in_cost": price,
        "stops": 0,
        "provider": provider,
        "fare_type": "basic",
        "warnings": [],
        "booking_url": f"https://example.invalid/flights?price={price}",
        "legs": [{
            "departure_airport": {"code": "BER", "name": "Berlin Brandenburg"},
            "arrival_airport": {"code": "FCO", "name": "Rome Fiumicino"},
            "departure_time": dep,
            "arrival_time": arr,
            "duration": 130,
            "airline": "Ryanair",
            "airline_code": "FR",
            "flight_number": flight_no,
        }],
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):        # noqa: N802
        body = json.dumps({"result": {"flights": FLIGHTS}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):       # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        self.do_GET()

    def log_message(self, *args):
        pass


def serve(port: int, price: float, real_price: float | None, with_real: bool) -> HTTPServer:
    global FLIGHTS
    FLIGHTS = [flight(price)]
    if with_real and real_price is not None:
        FLIGHTS.append(flight(real_price, provider="easyJet", flight_no="U2-1234",
                              dep="2026-10-31T09:15", arr="2026-10-31T11:05"))
    srv = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--price", type=float, default=0.01)
    ap.add_argument("--real-price", type=float, default=None)
    ap.add_argument("--only-broken", action="store_true",
                    help="nur den kaputten Tarif liefern")
    args = ap.parse_args()
    srv = serve(args.port, args.price, args.real_price, not args.only_broken)
    print(f"Stub laeuft auf http://127.0.0.1:{args.port} (Preis {args.price})", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
