#!/usr/bin/env python3
"""Multi-Kriterien-Score je Angebot (data-driven, Muster aus der Benchmark-Recherche).

Der bisherige Vergleich war reine Preissortierung ("billigster gewinnt"). Das
Scoring gewichtet mehrere Kriteriele (Preis, Stopps, Dauer, Abfahrtszeit, Gepäck),
nutzt harte Gates (z. B. erlaubte Stopps) als Ausschluss statt als Punkte und
normalisiert jedes Kriterium auf 0..1, damit die Gewichte vergleichbar sind.

Konfiguration (Registry, `defaults.scoring`):
    weights: {price: 1.0, stops: 0.35, duration: 0.25, depart_time: 0.15, baggage: 0.1}
    profiles:
      budget:   {price: 1.0, stops: 0.2,  duration: 0.1,  depart_time: 0.05, baggage: 0.0}
      comfort:  {price: 0.6, stops: 0.5,  duration: 0.5,  depart_time: 0.3,  baggage: 0.3}
    gates: {max_stops: 1}
"""
from __future__ import annotations

import math
from typing import Any


def _norm(value: float | None, best: float | None, worst: float | None,
          higher_is_better: bool = False) -> float | None:
    """0..1-Normalisierung innerhalb der Angebotsmenge (1 = best)."""
    if value is None or best is None or worst is None:
        return None
    if math.isclose(best, worst):
        return 1.0
    span = worst - best
    x = (value - best) / span
    x = max(0.0, min(1.0, x))
    return 1.0 - x if higher_is_better else x


def _duration_minutes(item: dict) -> float | None:
    dur = item.get("duration")
    if isinstance(dur, (int, float)):
        return float(dur)
    legs = item.get("legs") or []
    total = 0.0
    seen = False
    for leg in legs:
        d = leg.get("duration")
        if isinstance(d, (int, float)):
            total += float(d)
            seen = True
    return total if seen else None


def _depart_hour(item: dict) -> float | None:
    legs = item.get("legs") or []
    if not legs:
        return None
    t = str(legs[0].get("departure_time") or "")
    if len(t) >= 16 and t[11:13].isdigit():
        return float(t[11:13]) + float(t[14:16]) / 60.0
    return None


def _has_baggage(item: dict) -> float | None:
    """1 wenn Gepäck im Endpreis enthalten ist, 0 wenn nicht, None wenn unbekannt."""
    all_in = item.get("all_in")
    price = item.get("price")
    if all_in is None or price is None:
        return None
    if abs(all_in - price) < 0.01:
        return 1.0
    if item.get("bag_breakdown"):
        return 0.0
    return None


def score_offers(items: list[dict], cfg: dict | None = None,
                 profile: str | None = None) -> list[dict]:
    """Versieht jedes Angebot mit `score` (0..1) und `gate_failed` (Ausschlussgrund)."""
    cfg = cfg or {}
    weights = dict(cfg.get("weights") or {})
    profiles = cfg.get("profiles") or {}
    if profile and profile in profiles:
        weights = {**weights, **(profiles[profile] or {})}
    gates = cfg.get("gates") or {}

    if not items:
        return items

    prices = [i.get("price") for i in items if i.get("price") is not None]
    durs = [d for d in (_duration_minutes(i) for i in items) if d is not None]
    dep = [d for d in (_depart_hour(i) for i in items) if d is not None]
    stops = [s for s in (i.get("stops") for i in items) if isinstance(s, (int, float))]

    for it in items:
        # Gates: harte Ausschlusskriterien (z. B. zu viele Stopps)
        reasons = []
        if "max_stops" in gates and isinstance(it.get("stops"), (int, float)) \
                and it["stops"] > float(gates["max_stops"]):
            reasons.append(f"{it['stops']} Stopps > erlaubt {gates['max_stops']}")
        if "max_duration" in gates:
            d = _duration_minutes(it)
            if d is not None and d > float(gates["max_duration"]):
                reasons.append(f"Dauer {int(d)} min > erlaubt {gates['max_duration']}")
        it["gate_failed"] = "; ".join(reasons) if reasons else None

        total = 0.0
        weight_sum = 0.0
        parts = {}
        for key, weight in weights.items():
            if not weight:
                continue
            val = None
            best = worst = None
            if key == "price":
                val = it.get("all_in") if it.get("all_in") is not None else it.get("price")
                best, worst = (min(prices), max(prices)) if prices else (None, None)
                higher_is_better = False
            elif key == "stops":
                val = it.get("stops")
                best, worst = (min(stops), max(stops)) if stops else (None, None)
                higher_is_better = False
            elif key == "duration":
                val = _duration_minutes(it)
                best, worst = (min(durs), max(durs)) if durs else (None, None)
                higher_is_better = False
            elif key == "depart_time":
                val = _depart_hour(it)
                best, worst = (min(dep), max(dep)) if dep else (None, None)
                higher_is_better = False
            elif key == "arrival_time":
                val = _depart_hour(it)
                best, worst = (min(dep), max(dep)) if dep else (None, None)
                higher_is_better = False
            elif key == "baggage":
                val = _has_baggage(it)
                best, worst = (0.0, 1.0)
                higher_is_better = True
            else:
                continue
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                try:
                    val = float(val)
                except Exception:
                    continue      # nicht-numerisches Kriterium -> ueberspringen
            norm = _norm(val, best, worst, higher_is_better)
            if norm is None:
                continue
            parts[key] = round(norm, 3)
            total += norm * float(weight)
            weight_sum += float(weight)
        it["score_parts"] = parts
        it["score"] = round(total / weight_sum, 4) if weight_sum else None
    return items
