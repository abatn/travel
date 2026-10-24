"""GTFS-Fahrpläne (offener Standard) für Fähren und Bodentransport.

GTFS ist ein offener Standard (Google/Transit, CC BY 4.0 für die Spezifikation).
Viele Fähr- und Busbetreiber veröffentlichen ihre Fahrplandaten selbst als Feed.
**Enthalten sind Fahrpläne, keine Preise.**

Es werden nur die statischen Dateien gelesen: stops.txt, routes.txt, trips.txt,
stop_times.txt, calendar.txt (optional).
"""
from __future__ import annotations

import csv
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def _secs(value: str) -> int:
    """GTFS-Zeit (HH:MM:SS, darf > 24 sein) in Sekunden."""
    parts = (value or "").strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"ungültige GTFS-Zeit: {value!r}")
    h, m, s = (int(p) for p in parts)
    return h * 3600 + m * 60 + s


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


class GtfsFeed:
    """Minimaler statischer GTFS-Feed."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self.dir = Path(directory)
        if not self.dir.is_dir():
            raise FileNotFoundError(f"GTFS-Verzeichnis fehlt: {self.dir}")
        self.stops = {r["stop_id"]: r for r in _read_csv(self.dir / "stops.txt")}
        self.routes = {r["route_id"]: r for r in _read_csv(self.dir / "routes.txt")}
        self.trips = {r["trip_id"]: r for r in _read_csv(self.dir / "trips.txt")}
        self.stop_times: dict[str, list[dict[str, str]]] = {}
        for row in _read_csv(self.dir / "stop_times.txt"):
            self.stop_times.setdefault(row["trip_id"], []).append(row)
        for rows in self.stop_times.values():
            rows.sort(key=lambda r: int(r["stop_sequence"]))
        self.calendar: dict[str, dict[str, str]] = {}
        cal = self.dir / "calendar.txt"
        if cal.is_file():
            self.calendar = {r["service_id"]: r for r in _read_csv(cal)}

    # ------------------------------------------------------------ Abfragen
    def active_trips(self, day: date) -> list[str]:
        """Trips, die an diesem Wochentag laut calendar.txt verkehren."""
        if not self.calendar:
            return list(self.trips)
        weekday = day.strftime("%A").lower()
        start, end = day.strftime("%Y%m%d"), day.strftime("%Y%m%d")
        active = []
        for trip_id, trip in self.trips.items():
            cal = self.calendar.get(trip.get("service_id", ""))
            if not cal:
                continue
            if not (cal.get("start_date", "00000000") <= start <= cal.get("end_date", "99999999")):
                continue
            if cal.get(weekday) == "1":
                active.append(trip_id)
        return active

    def departures(self, from_stop: str, to_stop: str, day: date,
                   after: str | None = None) -> list[dict[str, Any]]:
        """Direkte Verbindungen zwischen zwei Haltestellen an einem Tag.

        `after` ist eine Uhrzeit (HH:MM). Es werden nur Trips berücksichtigt,
        bei denen `to_stop` nach `from_stop` angefahren wird.
        """
        from_stop = str(from_stop).strip()
        to_stop = str(to_stop).strip()
        if from_stop not in self.stops or to_stop not in self.stops:
            return []
        min_secs = _secs(after + ":00") if after else 0
        results: list[dict[str, Any]] = []
        for trip_id in self.active_trips(day):
            rows = self.stop_times.get(trip_id) or []
            board = next((r for r in rows if r["stop_id"] == from_stop), None)
            alight = next((r for r in rows if r["stop_id"] == to_stop), None)
            if not board or not alight:
                continue
            if int(board["stop_sequence"]) >= int(alight["stop_sequence"]):
                continue
            dep = _secs(board["departure_time"])
            if dep < min_secs:
                continue
            route = self.routes.get(self.trips[trip_id].get("route_id", ""), {})
            results.append({
                "trip_id": trip_id,
                "route": route.get("route_short_name") or route.get("route_long_name"),
                "from": self.stops[from_stop].get("stop_name"),
                "to": self.stops[to_stop].get("stop_name"),
                "departure": self._clock(dep),
                "arrival": self._clock(_secs(alight["arrival_time"])),
                "minutes": (_secs(alight["arrival_time"]) - dep) // 60,
            })
        results.sort(key=lambda r: r["departure"])
        return results

    @staticmethod
    def _clock(secs: int) -> str:
        """GTFS-Sekunden als HH:MM (auch > 24:00)."""
        return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}"

    @staticmethod
    def resolve_date(value: str | None) -> date:
        if not value:
            return date.today()
        return datetime.strptime(value, "%Y-%m-%d").date()

    def service_window(self, day: date) -> tuple[str, str]:
        """Nur zur Anzeige: erster und letzter Abfahrtszeitpunkt des Tages."""
        times = [
            _secs(r["departure_time"])
            for trip_id in self.active_trips(day)
            for r in self.stop_times.get(trip_id, [])
        ]
        if not times:
            return ("", "")
        return (self._clock(min(times)), self._clock(max(times)))
