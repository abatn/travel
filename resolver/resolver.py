#!/usr/bin/env python3
"""Orts-Resolver für alle vier Kategorien.

Löst Nutzereingaben (Stadtnamen, Tippfehler, Kürzel, deutsche Exonyme) in die
jeweils richtigen Codes auf:

* **Flüge**  -> IATA-Flughafencode (z. B. „Toulouse“ -> TLS, „frankfuhrt“ -> FRA)
* **Hotels** -> Stadt + Koordinaten (aus dem Flughafen-Datensatz)
* **Fähren** -> offizieller Hafenname (aus UN/LOCODE, Funktion „Hafen“)
* **Kreuzfahrten** -> 3-stelliger Hafen-Code, wie ihn die Reedereien verwenden
  (IATA, sonst UN/LOCODE-Ortsteil: Miami -> MIA, Hamburg -> HAM)

Datenquellen (Details: resolver/ENTSCHEIDUNG.md):
* Flughäfen/Städte: OurAirports (Public Domain), gefiltert auf Einträge mit IATA.
* Häfen: UN/LOCODE (UNECE, Aufbereitung ODC-PDDL-1.0), Funktion beginnt mit „1“.
* Deutsche Namen: kuratierte Alias-Tabelle (`data/aliases.csv`).

Kein Netzwerk nötig; alles lokal. Ergebnisse werden gecacht.
"""
from __future__ import annotations

import csv
import difflib
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
STATE = os.path.join(HERE, "state")
CACHE_PATH = os.path.join(STATE, "cache.json")

CATEGORIES = ("flights", "hotels", "ferries", "cruises")
MIN_SCORE = 0.62          # darunter gilt eine Eingabe als „nicht gefunden“

_airports: list[dict] | None = None
_ports: list[dict] | None = None
_aliases: dict[str, str] | None = None
_cache: dict | None = None


# ------------------------------------------------------------------ Normalisierung
def norm(text: str) -> str:
    """Kleinschreibung, Diakritika weg, Satzzeichen/Doppel-Leerzeichen normalisieren."""
    t = unicodedata.normalize("NFKD", str(text or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("ß", "ss").replace("ø", "o").replace("æ", "ae").replace("ł", "l")
    t = re.sub(r"[^a-z0-9]+", " ", t.casefold())
    return " ".join(t.split())


def load() -> None:
    """Daten einmal laden (lazy)."""
    global _airports, _ports, _aliases
    if _airports is not None:
        return
    with open(os.path.join(DATA, "airports.json"), encoding="utf-8") as fh:
        _airports = json.load(fh)
    with open(os.path.join(DATA, "ports.json"), encoding="utf-8") as fh:
        _ports = json.load(fh)
    _aliases = {}
    path = os.path.join(DATA, "aliases.csv")
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                _aliases.setdefault(norm(row["german"]), row["canonical"])


def _cache_read() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(CACHE_PATH, encoding="utf-8") as fh:
                _cache = json.load(fh)
        except Exception:
            _cache = {}
    return _cache


def _cache_write() -> None:
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(_cache or {}, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ------------------------------------------------------------------ Kandidaten
def _airport_candidates() -> list[tuple[str, dict]]:
    """(Suchtext, Airport) – Stadt, Name, Keywords, IATA."""
    load()
    out = []
    for a in _airports:
        keys = {norm(a["city"]), norm(a["name"])}
        for kw in (a.get("keywords") or "").split(","):
            if kw.strip():
                keys.add(norm(kw))
        for k in keys:
            if k:
                out.append((k, a))
    return out


def _port_candidates() -> list[tuple[str, dict, float]]:
    load()
    out = []
    for p in _ports:
        for k in {norm(p["name"]), norm(p.get("ascii") or "")}:
            if k:
                out.append((k, p, 0.10))
    return out


def _match_score(q: str, key: str) -> float:
    """Trefferqualität in Stufen - „Palma“ darf nicht „Palmar Norte“ schlagen."""
    if key == q:
        return 1.00
    if q in key.split():                 # ganzes Wort im Namen
        return 0.95
    if key.startswith(q + " "):          # Namensanfang („Palma de Mallorca“)
        return 0.93
    if key.startswith(q):                # Wortanfang („Palmar Norte“)
        return 0.85
    if q in key:                         # irgendwo enthalten
        return 0.80
    return difflib.SequenceMatcher(None, q, key).ratio()


def _best(text: str, candidates: list[tuple[str, dict]], limit: int = 5,
          category: str = "") -> list[tuple[float, dict]]:
    q = norm(text)
    if not q:
        return []
    scored: dict[str, tuple[float, dict]] = {}
    for key, obj, bonus in candidates:
        base = _match_score(q, key)
        if base < 0.80:
            # Fuzzy-Treffer (Tippfehler): nur wenn der Wortanfang passt oder die
            # Ähnlichkeit hoch ist - sonst wird aus „Xyzzy“ ein „Kyzyl“.
            same_start = len(q) >= 2 and len(key) >= 2 and q[:2] == key[:2]
            if not same_start and base < 0.80:
                continue
        score = base + bonus
        if score < MIN_SCORE:
            continue
        # Zusatzsignale: großer Flughafen mit Linienverkehr gewinnt Gleichstand
        if category in ("flights", "hotels"):
            if obj.get("type") == "large_airport":
                score += 0.03
            elif obj.get("type") == "medium_airport":
                score += 0.015
            if obj.get("scheduled") == "yes":
                score += 0.01
            if q in norm(obj.get("name")):
                score += 0.02
        ident = obj.get("iata") or obj.get("locode") or obj.get("name")
        best = scored.get(ident)
        if best is None or score > best[0]:
            # NICHT vor dem Sortieren kappen: sonst gehen Gleichstände verloren
            # (Rom: CIA und FCO beide 1.0 -> der falsche gewinnt).
            scored[ident] = (score, obj)
    return sorted(scored.values(), key=lambda x: -x[0])[:limit]


# ------------------------------------------------------------------ Auflösung
def _result(obj: dict, category: str, score: float, kind: str) -> dict:
    """Einheitliches Ergebnis je Kategorie."""
    if category == "flights":
        return {"code": obj["iata"], "kind": "iata", "name": obj["name"],
                "city": obj["city"], "country": obj.get("country"),
                "lat": _f(obj.get("lat")), "lon": _f(obj.get("lon")),
                "score": round(min(score, 1.0), 3)}
    if category == "hotels":
        return {"code": obj.get("iata"), "kind": "city", "name": obj["city"],
                "city": obj["city"], "country": obj.get("country"),
                "airport": obj.get("name"),
                "lat": _f(obj.get("lat")), "lon": _f(obj.get("lon")),
                "score": round(min(score, 1.0), 3)}
    if category == "ferries":
        return {"code": obj["locode"], "kind": "port", "name": obj["name"],
                "city": obj["name"], "country": obj.get("country"),
                "lat": _f(_coords(obj.get("coords"))[0]),
                "lon": _f(_coords(obj.get("coords"))[1]),
                "iata": obj.get("iata") or None, "score": round(min(score, 1.0), 3)}
    # cruises: 3-stelliger Hafen-Code (IATA bevorzugt, sonst LOCODE-Ortsteil)
    code = (obj.get("iata") or obj.get("loc") or obj["locode"][-3:]).upper()
    return {"code": code, "kind": "port_code", "name": obj["name"],
            "city": obj["name"], "country": obj.get("country"),
            "locode": obj["locode"],
            "lat": _f(_coords(obj.get("coords"))[0]),
            "lon": _f(_coords(obj.get("coords"))[1]),
            "score": round(min(score, 1.0), 3)}


def _f(value):
    try:
        return round(float(value), 6)
    except Exception:
        return None


def _coords(value: str | None) -> tuple[float | None, float | None]:
    """UN/LOCODE-Koordinaten „4230N 00131E“ -> Dezimalgrad."""
    m = re.match(r"(\d{4})([NS])\s+(\d{5})([EW])", str(value or ""))
    if not m:
        return None, None
    lat = int(m.group(1)[:2]) + int(m.group(1)[2:]) / 60
    lon = int(m.group(3)[:3]) + int(m.group(3)[3:]) / 60
    if m.group(2) == "S":
        lat = -lat
    if m.group(4) == "W":
        lon = -lon
    return round(lat, 6), round(lon, 6)


def resolve(text: str, category: str = "flights", use_cache: bool = True) -> dict:
    """Eingabe auflösen.

    Rückgabe: {"ok", "input", "category", "code", "name", "score",
               "alternatives": [{name, code, score}], "reason"}
    """
    load()
    category = category if category in CATEGORIES else "flights"
    q = str(text or "").strip()
    key = f"{category}|{norm(q)}"
    if use_cache:
        cached = _cache_read().get(key)
        if cached:
            out = dict(cached)
            out["cached"] = True
            return out

    base = {"input": q, "category": category, "ok": False, "cached": False}
    if not q:
        return {**base, "reason": "leere Eingabe"}

    # 1) Kürzel direkt (IATA 3 Zeichen / LOCODE 5 Zeichen)
    raw = q.upper().replace(" ", "")
    if category in ("flights", "hotels") and re.fullmatch(r"[A-Z]{3}", raw):
        hit = next((a for a in _airports if a["iata"] == raw), None)
        if hit:
            out = {**base, "ok": True, "reason": None,
                   **_result(hit, category, 1.0, "iata")}
            return _store(key, out)
    if category in ("ferries", "cruises") and re.fullmatch(r"[A-Z]{5}", raw):
        hit = next((p for p in _ports if p["locode"] == raw), None)
        if hit:
            out = {**base, "ok": True, "reason": None,
                   **_result(hit, category, 1.0, "locode")}
            return _store(key, out)

    # 2) deutsches Exonym - exakt oder als Tippfehler („Wienn“ -> Wien -> Vienna)
    search = _alias_lookup(q)

    # 3) Kandidaten bewerten
    if category == "flights":
        scored = _best(search, _candidate_airports_filtered(), category=category)
    elif category == "hotels":
        scored = _best(search, _candidate_airports_filtered(), category=category)
    else:
        scored = _best(search, _candidate_ports_filtered(), category=category)

    if not scored:
        return {**base, "reason": f"kein Ort für „{q}“ gefunden",
                "alternatives": []}

    score, obj = scored[0]
    out = {**base, "ok": True, "reason": None,
           **_result(obj, category, score, "fuzzy"),
           "alternatives": [
               {"name": _label(o, category), "code": _code(o, category),
                "score": round(s, 3)} for s, o in scored[1:4]]}
    return _store(key, out)


def _alias_lookup(text: str) -> str:
    """Alias exakt oder per Fuzzy (Tippfehler in deutschen Namen)."""
    q = norm(text)
    hit = _aliases.get(q)
    if hit:
        return hit
    if len(q) >= 4:
        close = difflib.get_close_matches(q, list(_aliases), n=1, cutoff=0.80)
        if close:
            return _aliases[close[0]]
    return text


def _label(obj: dict, category: str) -> str:
    if category in ("flights", "hotels"):
        return f"{obj['city']} ({obj['iata']}) – {obj['name']}"
    return f"{obj['name']} ({obj.get('iata') or obj['locode']})"


def _code(obj: dict, category: str) -> str:
    if category in ("flights", "hotels"):
        return obj["iata"]
    if category == "ferries":
        return obj["locode"]
    return (obj.get("iata") or obj.get("loc") or obj["locode"][-3:]).upper()


# ------------------------------------------------------------------ Filter
def _candidate_airports_filtered() -> list[tuple[str, dict]]:
    """Nur Flughäfen mit Linienverkehr (sonst tauchen Ackerstreifen auf)."""
    global _airport_cache
    try:
        return _airport_cache                       # type: ignore[name-defined]
    except NameError:
        pass
    load()
    small_types = {"heliport", "seaplane_base", "balloonport", "closed", "small_airport"}
    in_service = [a for a in _airports if a.get("scheduled") == "yes"]
    if not in_service:                              # Fallback, falls Feld fehlt
        in_service = [a for a in _airports if a.get("type") not in small_types]
    _airport_cache = _airport_candidates_of(in_service)   # type: ignore[name-defined]
    return _airport_cache


def _airport_candidates_of(airports: list[dict]) -> list[tuple[str, dict, float]]:
    """(Suchschlüssel, Datensatz, Bonus) – Stadt schlägt Flughafenname."""
    out = []
    for a in airports:
        city = norm(a["city"])
        if city:
            out.append((city, a, 0.10))
        name = norm(a["name"])
        if name:
            out.append((name, a, 0.0))
        for kw in (a.get("keywords") or "").split(","):
            k = norm(kw)
            if k:
                out.append((k, a, 0.02))
    return out


def _candidate_ports_filtered() -> list[tuple[str, dict]]:
    global _port_cache
    try:
        return _port_cache                           # type: ignore[name-defined]
    except NameError:
        pass
    load()
    # Nur echte Seehäfen (Funktion „1“) und mit Namen; Fähr-/Kreuzfahrtstauglich
    _port_cache = _port_candidates()                 # type: ignore[name-defined]
    return _port_cache


def _store(key: str, out: dict) -> dict:
    cache = _cache_read()
    cache[key] = out
    if len(cache) > 5000:                            # Ringpuffer
        for k in list(cache)[:1000]:
            cache.pop(k, None)
    _cache_write()
    return out


def suggestions(text: str, category: str = "flights", limit: int = 8) -> list[dict]:
    """Vorschläge für die Autocomplete (Name + Code + Score)."""
    load()
    category = category if category in CATEGORIES else "flights"
    alias = _alias_lookup(text)
    if category in ("flights", "hotels"):
        scored = _best(alias, _candidate_airports_filtered(), limit=limit * 2, category=category)
    else:
        scored = _best(alias, _candidate_ports_filtered(), limit=limit * 2, category=category)
    seen, out = set(), []
    for s, obj in scored:
        key = _code(obj, category)
        if key in seen:
            continue
        seen.add(key)
        out.append({"label": _label(obj, category), "code": key,
                    "score": round(s, 3)})
        if len(out) >= limit:
            break
    return out


def stats() -> dict:
    load()
    return {"airports": len(_airports), "airports_scheduled":
            sum(1 for a in _airports if a.get("scheduled") == "yes"),
            "ports": len(_ports), "aliases": len(_aliases or {}),
            "cache_entries": len(_cache_read())}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(json.dumps(stats(), ensure_ascii=False, indent=1))
        raise SystemExit(0)
    cat = sys.argv[2] if len(sys.argv) > 2 else "flights"
    print(json.dumps(resolve(sys.argv[1], cat), ensure_ascii=False, indent=1))
