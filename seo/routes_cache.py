#!/usr/bin/env python3
"""Zwischenspeicher der letzten Suchläufe je Route (nur für indexierbare Seiten).

Warum: Die Lauf-Ergebnisseiten (/jobs/<id>) sind nutzerspezifisch und werden nicht
indexiert. Für Suchmaschinen brauchen wir **dauerhafte** Seiten mit echten Preisen.
Also merkt sich die Oberfläche nach jedem erfolgreichen Lauf die wichtigsten
Angebote je Route (z. B. flights/BER-FCO) und rendert daraus die Routenseite
/fluege/ber-fco – inklusive Preisstand und dem Hinweis, dass der Preis beim
Anbieter verbindlich ist.

Gespeichert wird **nur**, was die Quellen geliefert haben (keine Berechnung,
keine Schätzung); der Zeitstempel steht in der Datei und auf der Seite.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE_DIR = os.path.join(ROOT, "ui", "state", "routes")

SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def _slug(value: str) -> str:
    return SAFE.sub("-", str(value or "").strip()).strip("-").upper() or "X"


def route_id(origin: str, destination: str) -> str:
    return f"{_slug(origin)}-{_slug(destination)}"


def _path(category: str, route: str) -> str:
    return os.path.join(CACHE_DIR, category, f"{route}.json")


def save(category: str, origin: str, destination: str, offers: list[dict],
         params: dict | None = None) -> str | None:
    """Angebote einer Route ablegen (max. 10, nur mit Preis)."""
    if not origin or not destination or not offers:
        return None
    # S3: Qualitätsgate - keine dünnen oder offensichtlich falschen Routen speichern
    cleaned_input = [it for it in offers if it.get("price") is not None]
    if len(cleaned_input) < 5:
        return None                      # zu wenig Angebote -> keine eigene Seite
    for code in (origin, destination):
        token = str(code).strip()
        if not (2 <= len(token) <= 40) or token.startswith("-"):
            return None
    cleaned = []
    for it in offers[:10]:
        if it.get("price") is None:
            continue
        cleaned.append({
            "name": it.get("name") or it.get("provider"),
            "provider": it.get("provider"),
            "price": it.get("price"),
            "currency": it.get("currency"),
            "all_in": it.get("all_in"),
            "stops": it.get("stops"),
            "url": it.get("booking_url"),
            "source": it.get("source"),
            "price_scope": it.get("price_scope"),
        })
    if not cleaned:
        return None
    # Ortsnamen aus den Flugabschnitten (echte Daten der Quelle, keine Zuordnungstabelle)
    origin_name = destination_name = None
    for it in offers:
        legs = it.get("legs") or []
        if legs:
            try:
                origin_name = (legs[0].get("departure_airport") or {}).get("name") or None
                destination_name = (legs[-1].get("arrival_airport") or {}).get("name") or None
            except Exception:
                origin_name = destination_name = None
            if origin_name and destination_name:
                break
    route = route_id(origin, destination)
    path = _path(category, route)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "category": category,
        "route": route,
        "origin": origin,
        "destination": destination,
        "origin_name": origin_name,
        "destination_name": destination_name,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "params": params or {},
        "offers": cleaned,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    return path


def load(category: str, route: str) -> dict | None:
    try:
        with open(_path(category, route), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def list_routes(category: str) -> list[dict]:
    """Alle gespeicherten Routen einer Kategorie (neueste zuerst)."""
    folder = os.path.join(CACHE_DIR, category)
    out = []
    if not os.path.isdir(folder):
        return out
    for name in os.listdir(folder):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        data["_route"] = name[:-5]
        out.append(data)
    out.sort(key=lambda d: d.get("generated_at") or "", reverse=True)
    return out


def all_routes() -> list[dict]:
    out = []
    for category in ("flights", "hotels", "ferries", "cruises"):
        out.extend(list_routes(category))
    return out


def facts(data: dict | None) -> dict:
    """Aus den echten Angeboten berechnete Strecken-Fakten (kein erfundener Text)."""
    if not data:
        return {}
    offers = [o for o in (data.get("offers") or []) if o.get("price") is not None]
    if not offers:
        return {}
    prices = sorted(float(o["price"]) for o in offers)
    providers: dict[str, int] = {}
    for o in offers:
        name = (o.get("provider") or o.get("name") or "").strip()
        if name:
            providers[name] = providers.get(name, 0) + 1
    nonstop = sum(1 for o in offers if o.get("stops") == 0)
    star_offers = [o for o in offers if o.get("all_in") is not None]
    sources = sorted({o.get("source") for o in offers if o.get("source")})
    return {
        "count": len(offers),
        "min_price": round(prices[0], 2),
        "max_price": round(prices[-1], 2),
        "median_price": round(prices[len(prices) // 2], 2),
        "nonstop": nonstop,
        "nonstop_share": round(nonstop / len(offers) * 100),
        "airlines": [n for n, _ in sorted(providers.items(), key=lambda kv: -kv[1])][:3],
        "sources": sources,
        "with_end_price": len(star_offers),
        "currency": offers[0].get("currency") or "EUR",
    }


def age_hours(data: dict) -> float | None:
    try:
        ts = datetime.fromisoformat(str(data.get("generated_at")))
        now = datetime.now(timezone.utc).astimezone()
        return max(0.0, (now - ts).total_seconds() / 3600.0)
    except Exception:
        return None
