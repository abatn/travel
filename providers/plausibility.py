#!/usr/bin/env python3
"""Plausibilitätsprüfung für Preise.

Eine Quelle kann formal gültige Antworten liefern und dabeiUnsinn melden
(z. B. 0,01 EUR statt 180 EUR). Solche Werte dürfen weder als „günstigstes
Angebot" erscheinen noch den Vergleich verfälschen.

Drei Regeln (Konfiguration in `providers/registry.yaml`, Abschnitt `defaults.plausibility`):

1. **Absolute Untergrenze** – ein Preis unter `min_price` ist unplausibel
   (0,01 EUR ist kein Flugpreis).
2. **Verhältnis zum Markt** – ein Preis unter `max_ratio_to_median` des Medians
   aller antwortenden Quellen ist unplausibel (1 EUR bei einem Median von 180 EUR).
   Der Vergleich greift erst ab `min_sources_for_ratio` antwortenden Quellen.
3. **Auffällige Werte** – exakte Treffer aus `suspicious_values` (typische Fehlerpreise).

Wird eine Regel verletzt, wird das Angebot **verworfen** (nicht nur abgewertet),
mit Begründung markiert und die Quelle als *korrupt* gemeldet. Die Angebote einer
als korrupt gemeldeten Quelle werden nicht für den Vergleich verwendet - die
Quelle liefert dann keine belastbare Preisauskunft mehr.
"""
from __future__ import annotations

import statistics


def _cfg(cfg: dict | None) -> dict:
    cfg = cfg or {}
    out = {
        "enabled": True,
        "min_price": 1.0,
        "max_ratio_to_median": 0.25,
        "min_sources_for_ratio": 3,
        "suspicious_values": [0.01, 0.1, 0.5, 1.0],
        "max_ratio_within_source": 0.15,   # Ausreisser innerhalb einer Quelle
        "min_items_within_source": 2,
        "min_price_by_category": {},        # fachliche Untergrenze je Kategorie
        "scope": "per_person",
    }
    out.update({k: v for k, v in cfg.items() if k in out})
    return out


def item_price(item: dict) -> float | None:
    try:
        p = item.get("price")
        return float(p) if p is not None else None
    except Exception:
        return None


def scope_of(item: dict) -> str:
    """Preisbasis eines Angebots (leer = unbekannt)."""
    scope = item.get("price_scope")
    if not scope:
        conf = item.get("price_scope_confidence")
        scope = "unbekannt" if not conf else str(scope)
    return str(scope or "unbekannt")


def floor_for(category: str | None, cfg: dict | None = None) -> float:
    """Fachliche Untergrenze fuer die Kategorie (flaeche Obergrenze als Rueckfall)."""
    c = _cfg(cfg)
    floors = c.get("min_price_by_category") or {}
    try:
        val = floors.get(str(category))
        if val is not None:
            return float(val)
    except Exception:
        pass
    return float(c.get("min_price") or 0)


def check_item(item: dict, market_median: float | None, cfg: dict | None = None,
               category: str | None = None) -> str | None:
    """Gibt eine Begründung zurueck, wenn das Angebot unplausibel ist, sonst None."""
    c = _cfg(cfg)
    if not c["enabled"]:
        return None
    price = item_price(item)
    if price is None:
        return None
    if price <= 0:
        return f"Preis {price} ist kein gueltiger Preis (<= 0)"
    try:
        suspicious = [float(v) for v in (c.get("suspicious_values") or [])]
    except Exception:
        suspicious = []
    if any(abs(price - v) < 0.005 for v in suspicious):
        return f"Preis {price} entspricht einem typischen Fehlerwert (auffaelliger Wert)"
    min_price = floor_for(category, c)
    if min_price and price < min_price:
        return (f"Preis {price} liegt unter der fachlichen Untergrenze {min_price} "
                f"fuer die Kategorie '{category or 'unbekannt'}' (unplausibel)")
    own = item.get("_source_median")
    own_ratio = float(c.get("max_ratio_within_source") or 0)
    min_items = int(c.get("min_items_within_source") or 0)
    if own and own_ratio and own > 0 and price < own * own_ratio:
        return (f"Preis {price} liegt bei {round(price / own * 100, 1)} % des Medians der "
                f"eigenen Quelle ({round(own, 2)}) (Grenze {round(own_ratio * 100, 0)} %) - "
                f"typischer Datenfehler dieser Quelle")
    ratio = float(c.get("max_ratio_to_median") or 0)
    min_sources = int(c.get("min_sources_for_ratio") or 0)
    if ratio and market_median and market_median > 0:
        if price < market_median * ratio:
            return (f"Preis {price} liegt bei {round(price / market_median * 100, 1)} % des "
                    f"Marktmedians {round(market_median, 2)} (Grenze "
                    f"{round(ratio * 100, 0)} %) - unplausibel")
    return None


def market_median(items: list[dict], cfg: dict | None = None) -> tuple[float | None, int]:
    """Median ueber alle Quellen (nur fuer die Gesamtausgabe)."""
    c = _cfg(cfg)
    cheapest_per_source: dict[str, float] = {}
    for it in items:
        p = item_price(it)
        src = str(it.get("source"))
        if p is None or p <= 0:
            continue
        if src not in cheapest_per_source or p < cheapest_per_source[src]:
            cheapest_per_source[src] = p
    if len(cheapest_per_source) < int(c.get("min_sources_for_ratio") or 0):
        return None, len(cheapest_per_source)
    return statistics.median(list(cheapest_per_source.values())), len(cheapest_per_source)


def scope_medians(items: list[dict], cfg: dict | None = None) -> dict[str, tuple[float, int]]:
    """Je Preisbasis ein eigener Marktmedian (Anzahl Quellen dahinter)."""
    c = _cfg(cfg)
    per_scope: dict[str, dict[str, float]] = {}
    for it in items:
        p = item_price(it)
        if p is None or p <= 0:
            continue
        scope = scope_of(it)
        src = str(it.get("source"))
        bucket = per_scope.setdefault(scope, {})
        if src not in bucket or p < bucket[src]:
            bucket[src] = p
    out: dict[str, tuple[float, int]] = {}
    for scope, bucket in per_scope.items():
        if len(bucket) >= int(c.get("min_sources_for_ratio") or 0):
            out[scope] = (statistics.median(list(bucket.values())), len(bucket))
    return out


def screen(items: list[dict], cfg: dict | None = None, category: str | None = None) -> dict:
    """Prüft alle Angebote.

    Rückgabe:
        rejected      – verworfene Angebote (mit Begründung)
        corrupt       – Quellen, die mindestens einen unplausiblen Preis geliefert haben
        kept_sources  – Quellen, deren Angebote verwendet werden dürfen
        median        – Marktmedian, gegen den geprüft wurde
    """
    c = _cfg(cfg)
    median, n_sources = market_median(items, c)
    per_scope = scope_medians(items, c)
    rejected: list[dict] = []
    corrupt: dict[str, list[str]] = {}
    # Median je Quelle (fuer die Ausreisserpruefung innerhalb der Quelle)
    per_source: dict[str, list[float]] = {}
    for it in items:
        p = item_price(it)
        if p is None or p <= 0:
            continue
        per_source.setdefault(str(it.get("source")), []).append(p)
    source_medians = {src: statistics.median(vals) for src, vals in per_source.items()
                      if len(vals) >= int(c.get("min_items_within_source") or 2)}
    for it in items:
        scope = scope_of(it)
        scope_info = per_scope.get(scope)
        # Vergleich nur innerhalb derselben Preisbasis (sonst Fehlalarme)
        probe = dict(it)
        probe["_source_median"] = source_medians.get(str(it.get("source")))
        reason = check_item(probe, scope_info[0] if scope_info else None, c, category)
        if reason:
            src = str(it.get("source"))
            corrupt.setdefault(src, []).append(reason)
            rejected.append({"source": src, "price": it.get("price"),
                             "currency": it.get("currency"), "reason": reason,
                             "provider": it.get("provider")})
    return {"rejected": rejected,
            "corrupt": corrupt,
            "floor": floor_for(category, c),
            "category": category,
            "kept_sources": sorted({str(it.get("source")) for it in items} - set(corrupt)),
            "median": round(median, 2) if median else None,
            "sources_compared": n_sources,
            "scope_medians": {k: [round(v[0], 2), v[1]] for k, v in per_scope.items()}}


def message_for_source(source: str, reasons: list[str]) -> str:
    """Fehlermeldung fuer die Protokollausgabe."""
    return (f"Quelle liefert korrupte Daten: {len(reasons)} Angebot(e) mit unplausiblen "
            f"Preisen - {reasons[0]}. Tarife dieser Quelle werden nicht verwendet.")


def message_global(rejected: list[dict], corrupt: dict) -> str:
    """Gesamtmeldung fuer die Ausgabe."""
    if not rejected:
        return ""
    parts = [f"{r['source']}: {r['price']} {r.get('currency') or ''} ({r['reason']})"
             for r in rejected[:5]]
    return ("FEHLER - korrupte Preisdaten von "
            f"{len(corrupt)} Quelle(n): " + "; ".join(parts)
            + ("; ..." if len(rejected) > 5 else ""))
