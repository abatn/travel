"""Normalisierung der Provider-Antworten – rein datengetrieben (Pfade aus der Registry).

Der Extraktionsblock einer Quelle in `registry.yaml` beschreibt, wo Preise, Währung,
Stopps, Koordinaten usw. stehen. Neue Quellen brauchen daher **keinen Code**, nur Config.
"""
from __future__ import annotations

import re
from typing import Any

MISSING = object()


def get_path(obj: Any, path: str | None, default: Any = None) -> Any:
    """Punktpfad-Auflösung, z. B. "result.flights" oder "hotels". Listenindizes via [0]."""
    if not path:
        return default
    cur = obj
    for part in path.split("."):
        if cur is None:
            return default
        m = re.fullmatch(r"([^\[\]]+)\[(\d+)\]", part)
        if m:
            key, idx = m.group(1), int(m.group(2))
            if not isinstance(cur, dict) or key not in cur:
                return default
            cur = cur[key]
            if not isinstance(cur, list) or idx >= len(cur):
                return default
            cur = cur[idx]
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return default
        else:
            return default
    return default if cur is None else cur


def first_present(item: dict, spec: Any, default: Any = None) -> Any:
    """Erster nicht-leerer Wert aus einer Pfadliste (auch Liste erlaubt)."""
    if spec is None:
        return default
    paths = spec if isinstance(spec, list) else [spec]
    for p in paths:
        val = get_path(item, p, MISSING)
        if val is not MISSING and val not in (None, "", [], {}):
            return val
    return default


def normalize_item(item: dict, extract: dict, source_id: str, category: str) -> dict:
    """Vereinheitlicht ein Rohangebot auf das gemeinsame Schema.

    `extract.price_divisor` (optional, additiv): Quellen, die Preise in Cent liefern
    (z. B. Ferryhopper-MCP `totalPriceInCents`, Finnlines-GraphQL `chargeTotal`),
    werden durch Division auf die Einheit der Währung gebracht (100 = Cent -> EUR).
    """
    price = first_present(item, extract.get("price"))
    currency = first_present(item, extract.get("currency"))
    if currency is None:
        # Konstante Waehrung: extract.currency darf ein 3-stelliges ISO-Kuerzel
        # sein (z. B. "EUR"), wenn die Antwort selbst kein Waehrungsfeld fuehrt.
        spec = extract.get("currency")
        if isinstance(spec, str) and re.fullmatch(r"[A-Z]{3}", spec):
            currency = spec
    all_in = first_present(item, extract.get("all_in"))
    divisor = extract.get("price_divisor")
    try:
        divisor = float(divisor) if divisor else 1.0
    except (TypeError, ValueError):
        divisor = 1.0
    if divisor not in (0.0, 1.0):
        price = _num(price)
        all_in = _num(all_in)
        if price is not None:
            price = price / divisor
        if all_in is not None:
            all_in = all_in / divisor
    item_extra: dict = {}
    name = first_present(item, extract.get("name"))
    lat = first_present(item, extract.get("lat"))
    lon = first_present(item, extract.get("lon"))
    stops = first_present(item, extract.get("stops"))
    # Anzahl statt Liste: manche Quellen liefern Segmente als Liste (z. B. alice-flights)
    for key, path in (extract.get("counts") or {}).items():
        lst = first_present(item, path, None)
        if isinstance(lst, list):
            val = max(0, len(lst) - 1)     # Anzahl Elemente minus 1 = Stopps
            if key == "stops" and stops is None:
                stops = val
            else:
                item_extra[key] = val
    if stops is None and extract.get("stops_sum"):
        segs = first_present(item, extract.get("stops_sum"), [])
        if isinstance(segs, list):
            total = 0
            for seg in segs:
                if isinstance(seg, dict):
                    try:
                        total += int(seg.get("stopCount", 0) or 0)
                    except Exception:
                        pass
            stops = total
    return {
        "source": source_id,
        "category": category,
        "name": name,
        "price_raw": _num(price),
        "price": _num(price),
        "currency": currency,
        "all_in": _num(all_in),
        "bag_breakdown": first_present(item, extract.get("bag_breakdown")),
        "stops": stops,
        "stars": first_present(item, extract.get("stars")),
        "provider": first_present(item, extract.get("provider")),
        "booking_url": first_present(item, extract.get("booking_url")),
        "warnings": first_present(item, extract.get("warnings"), []),
        "legs": first_present(item, extract.get("legs"), []),
        "lat": _num(lat),
        "lon": _num(lon),
        "entity_key": first_present(item, extract.get("entity_key")),
        "identity": first_present(item, extract.get("identity")),
        **item_extra,
        # --- Kreuzfahrten (additiv, 2026-10-21) -------------------------
        "departure_date": first_present(item, extract.get("departure_date")),
        "return_date": first_present(item, extract.get("return_date")),
        "nights": _num(first_present(item, extract.get("nights"))),
        "boarding": first_present(item, extract.get("boarding")),
        "destination": first_present(item, extract.get("destination")),
        "all_inclusive": first_present(item, extract.get("all_inclusive")),
        "taxes_included": first_present(item, extract.get("taxes_included")),
        "drinks_included": first_present(item, extract.get("drinks_included")),
        "raw": item,
    }


def parse_markdown_table(text: str, spec: dict, source_id: str, category: str) -> list[dict]:
    """Markdown-Tabelle (z. B. MCP-Antworten ohne JSON) in Angebote übersetzen.

    Spaltenzuordnung kommt aus der Registry (`extract.table`), damit keine
    quellenspezifische Logik im Code steckt.
    """
    import re as _re
    rows: list[dict] = []
    price_re = spec.get("price_regex")
    stops_re = spec.get("stops_regex")
    url_re = spec.get("url_regex")
    price_col = spec.get("price_col", 0)
    stops_col = spec.get("stops_col")
    name_col = spec.get("name_col")
    url_col = spec.get("url_col", -1)
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or set("".join(cells)) <= set("-: "):
            continue  # Trennzeile
        if cells[0].lower() in ("price", "hotel", "provider"):
            continue  # Kopfzeile
        item: dict = {"source": source_id, "category": category}
        raw_price = cells[price_col] if -len(cells) <= price_col < len(cells) else ""
        price = None
        if price_re:
            m = _re.search(price_re, raw_price.replace(",", ".") if "," in raw_price else raw_price)
            if m:
                try:
                    price = float(m.group(1) if m.groups() else m.group(0))
                except Exception:
                    price = None
        if price is None:
            price = _num(raw_price)
        if price is None:
            continue
        item["price"] = price
        item["currency"] = None
        if stops_col is not None and -len(cells) <= stops_col < len(cells) and stops_re:
            m = _re.search(stops_re, cells[stops_col])
            if m:
                try:
                    item["stops"] = int(m.group(1))
                except Exception:
                    item["stops"] = None
        if name_col is not None and -len(cells) <= name_col < len(cells):
            item["name"] = cells[name_col]
        if url_col is not None and -len(cells) <= url_col < len(cells) and url_re:
            m = _re.search(url_re, cells[url_col])
            if m:
                item["booking_url"] = m.group(1)
        item.setdefault("stops", None)
        item.setdefault("name", None)
        item.setdefault("booking_url", None)
        item.setdefault("all_in", None)
        item.setdefault("provider", source_id)
        item.setdefault("currency", None)
        item.setdefault("warnings", [])
        item.setdefault("legs", [])
        rows.append(item)
    return rows


def parse_text_prices(text: str, spec: dict, source_id: str, category: str) -> list[dict]:
    """Antwort im Fließtext (z. B. 'EUR 289.31') -> Angebote via Regex."""
    import re as _re
    price_re = spec.get("price_regex", r"([A-Z]{3})\s*([0-9]+[.,]?[0-9]*)")
    rows: list[dict] = []
    for m in _re.finditer(price_re, text or ""):
        # Preis ist die LETZTE Gruppe; eine erste Gruppe kann die Waehrung sein.
        groups = [g for g in m.groups() if g is not None]
        if not groups:
            continue
        price_group = groups[-1]
        ccy_group = groups[0] if len(groups) > 1 else None
        try:
            price = float(str(price_group).replace(",", "."))
        except Exception:
            continue
        item = {"source": source_id, "category": category, "price": price,
                "currency": ccy_group,
                "name": spec.get("name"), "provider": spec.get("provider") or source_id,
                "all_in": None, "bag_breakdown": None, "stops": None,
                "booking_url": None, "warnings": [], "legs": []}
        rows.append(item)
        if len(rows) >= int(spec.get("max_items", 25)):
            break
    return rows


def normalize_expanded(parent: dict, rate: dict, expand: dict, source_id: str,
                       category: str) -> dict:
    """Ein Angebot aus einem Parent-Objekt plus einem Eintrag einer Rate-Liste.

    Beispiel (Hotel mit mehreren OTA-Raten): Parent = Hotel, Rate = eine Ratenzeile.
    """
    merged = dict(parent)
    merged.update(rate)
    if expand.get("name_from_parent"):
        merged["name"] = parent.get("name")   # Hotelname statt Zimmername
    item = normalize_item(merged, expand, source_id, category)
    # Stammdaten des Hotels behalten, falls die Rate sie nicht führt
    for key in ("name", "stars", "lat", "lon", "entity_key"):
        if item.get(key) is None:
            item[key] = first_present(parent, {"name": "name", "stars": "stars",
                                               "lat": "lat", "lon": "lon",
                                               "entity_key": "entity_key"}[key])
    return item


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:[.,]\d+)?", v.replace(" ", ""))
        if m:
            try:
                return float(m.group(0).replace(",", "."))
            except Exception:
                return None
    return None


def dedupe(items: list[dict]) -> list[dict]:
    """Identische Tarife desselben Anbieters zusammenfassen (Preis + Stops + Key).

    `departure_date` ist Teil des Keys, damit bei Kreuzfahrten mehrere Abfahrten
    desselben Itinerariums mit identischem Preis nicht zusammengefasst werden.
    Fuer Fluege/Hotels ist das Feld nicht gesetzt -> Verhalten unveraendert.
    """
    seen: dict[tuple, dict] = {}
    out: list[dict] = []
    for it in items:
        # Identitaet bevorzugt: Angebots-ID der Quelle (ein Angebot ist ein Angebot,
        # nicht "irgendein Flug zum gleichen Preis").
        ident = it.get("identity")
        if ident:
            key = (str(it.get("source")), "id:" + str(ident))
        else:
            key = (str(it.get("source")), str(it.get("name")), str(it.get("price")),
                   str(it.get("stops")), str(it.get("provider")),
                   str(it.get("departure_date")))
        if key in seen:
            prev = seen[key]
            # Endpreis bevorzugen, wenn vorhanden
            if prev.get("all_in") is None and it.get("all_in") is not None:
                prev["all_in"] = it["all_in"]
                prev["bag_breakdown"] = it.get("bag_breakdown")
            continue
        seen[key] = it
        out.append(it)
    return out


def rank_key(item: dict, rank_by: str = "price", nights: int = 1) -> tuple:
    """Sortierschlüssel:
    'price'   = Basispreis
    'all_in'  = Endpreis (Fallback Basispreis)
    'score'   = Multi-Kriterien-Score (Gate-Verstoß fällt zurück)
    'value'   = Preis je Person und Tag
    """
    if rank_by == "all_in":
        return (item.get("all_in") if item.get("all_in") is not None else
                item.get("price") if item.get("price") is not None else 1e12,
                item.get("price") if item.get("price") is not None else 1e12)
    if rank_by == "score":
        gate = 1 if item.get("gate_failed") else 0
        sc = item.get("score")
        return (gate, -(sc if sc is not None else -1e12),
                item.get("all_in") if item.get("all_in") is not None else
                item.get("price") if item.get("price") is not None else 1e12)
    if rank_by == "value":
        days = max(1, int(nights or 1))
        pr = item.get("all_in") if item.get("all_in") is not None else item.get("price")
        return (pr / days if pr is not None else 1e12,)
    return (item.get("price") if item.get("price") is not None else 1e12,)
