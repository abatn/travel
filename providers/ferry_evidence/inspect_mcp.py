#!/usr/bin/env python3
"""MCP-Antwort (ferry_evidence/*.json) auswerten: Preisfelder, Währung, Verfügbarkeit."""
from __future__ import annotations

import json
import sys


def load(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def structured(d):
    r = d.get("call", {}).get("result", {})
    sc = r.get("structuredContent")
    if sc is None:
        txt = "".join(x.get("text", "") for x in r.get("content", []))
        try:
            sc = json.loads(txt)
        except Exception:
            return {"__text__": txt}
    return sc


def walk_prices(obj, path=""):
    """Alle Felder finden, deren Name auf Preis/amount/currency hindeutet."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            kl = k.lower()
            if kl in ("price", "amount", "fare", "total", "totalprice", "priceamount",
                      "adultprice", "vehicleprice", "cabinprice", "fromprice", "minprice",
                      "discountprice", "grandtotal", "priceformatted", "fareamount"):
                out.append((p, v))
            out.extend(walk_prices(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(walk_prices(v, f"{path}[{i}]"))
    return out


def main():
    path = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    d = load(path)
    sc = structured(d)
    if "__text__" in sc:
        print("TEXT-ANTWORT:", sc["__text__"][:1500])
        return
    print("TOP-LEVEL KEYS:", list(sc.keys()))
    txt = json.dumps(sc, ensure_ascii=False, indent=1)
    print("LEN:", len(txt))
    print(txt[:limit * 400])


if __name__ == "__main__":
    main()
