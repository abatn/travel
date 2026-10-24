"""Flughafen-Referenzdaten aus OurAirports (Public Domain).

Quelle: https://github.com/davidmegginson/ourairports-data (CSV, Public Domain).
Enthält keine Preise – nur Stammdaten (IATA/ICAO, Name, Stadt, Land, Koordinaten).

Die CSV wird nicht mitgeliefert. Pfad über `AIRPORTS_CSV` oder explizit:
    export AIRPORTS_CSV=/pfad/zu/airports.csv
"""
from __future__ import annotations

import csv
import math
import os
from pathlib import Path
from typing import Any


def _clean(value: str | None) -> str:
    return (value or "").strip().strip('"')


def _to_float(value: str | None) -> float | None:
    try:
        return float(_clean(value))
    except (TypeError, ValueError):
        return None


def load_airports(path: str | os.PathLike[str] | None = None) -> dict[str, dict[str, Any]]:
    """Liest die OurAirports-CSV und liefert ein Dict nach IATA-Code.

    Zeilen ohne IATA-Code (z. B. kleine Flugplätze) werden übersprungen.
    """
    csv_path = Path(path or os.getenv("AIRPORTS_CSV", ""))
    if not csv_path or not csv_path.is_file():
        raise FileNotFoundError(
            "OurAirports-CSV fehlt. Setze AIRPORTS_CSV (z. B. airports.csv aus "
            "github.com/davidmegginson/ourairports-data)."
        )
    airports: dict[str, dict[str, Any]] = {}
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            iata = _clean(row.get("iata_code")).upper()
            if len(iata) != 3:
                continue
            airports[iata] = {
                "iata": iata,
                "icao": _clean(row.get("icao_code")).upper() or None,
                "name": _clean(row.get("name")),
                "city": _clean(row.get("municipality")) or None,
                "country": _clean(row.get("iso_country")) or None,
                "type": _clean(row.get("type")) or None,
                "lat": _to_float(row.get("latitude_deg")),
                "lon": _to_float(row.get("longitude_deg")),
                "scheduled_service": _clean(row.get("scheduled_service")) == "yes",
            }
    return airports


def lookup(iata: str, airports: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    return airports.get(str(iata).strip().upper())


def search(city: str, airports: dict[str, dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """Sucht nach Stadt- oder Flughafennamen (Teiltreffer, case-insensitive)."""
    needle = str(city).strip().lower()
    if not needle:
        return []
    hits = [
        a for a in airports.values()
        if needle in (a.get("city") or "").lower() or needle in (a.get("name") or "").lower()
    ]
    hits.sort(key=lambda a: ((a.get("city") or "").lower() != needle, a["iata"]))
    return hits[:limit]


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine-Distanz in Kilometern."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest(lat: float, lon: float, airports: dict[str, dict[str, Any]],
            limit: int = 5, max_km: float = 500.0) -> list[dict[str, Any]]:
    """Nächstgelegene Flughäfen mit planmäßigem Linienverkehr."""
    out = []
    for airport in airports.values():
        if not airport.get("scheduled_service"):
            continue
        if airport.get("lat") is None or airport.get("lon") is None:
            continue
        dist = distance_km(lat, lon, airport["lat"], airport["lon"])
        if dist <= max_km:
            out.append({**airport, "distance_km": round(dist, 1)})
    out.sort(key=lambda a: a["distance_km"])
    return out[:limit]
