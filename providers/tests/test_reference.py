#!/usr/bin/env python3
"""Tests für Referenzdaten (OurAirports) und GTFS-Fahrpläne – ohne Netzwerk."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "providers"))

from reference.airports import distance_km, load_airports, lookup, nearest, search  # noqa: E402
from reference.gtfs import GtfsFeed  # noqa: E402

AIRPORTS_CSV = """id,ident,type,name,latitude_deg,longitude_deg,elevation_ft,continent,iso_country,iso_region,municipality,scheduled_service,icao_code,iata_code,gps_code,local_code
1,EDDB,large_airport,Berlin Brandenburg,52.3667,13.5033,157,EU,DE,DE-BE,Berlin,yes,EDDB,BER,EDDB,
2,LIRF,large_airport,Rome Fiumicino,41.8003,12.2389,15,EU,IT,IT-RM,Rome,yes,LIRF,FCO,LIRF,
3,EDDF,large_airport,Frankfurt am Main,50.0333,8.5706,364,EU,DE,DE-HE,Frankfurt,yes,EDDF,FRA,EDDF,
4,XXXX,small_airport,Privatplatz,50.0,8.0,0,EU,DE,DE-HE,Dorf,no,,,,
"""


def _write_gtfs(directory: Path) -> None:
    (directory / "stops.txt").write_text(
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "A,Ancona,43.6,13.5\n"
        "B,Igoumenitsa,39.5,20.2\n"
        "C,Zwischenhalt,41.0,17.0\n", encoding="utf-8")
    (directory / "routes.txt").write_text(
        "route_id,route_short_name,route_long_name\n"
        "R1,F1,Adria Linie\n", encoding="utf-8")
    (directory / "trips.txt").write_text(
        "route_id,service_id,trip_id\n"
        "R1,S1,T1\nR1,S1,T2\n", encoding="utf-8")
    (directory / "stop_times.txt").write_text(
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T1,08:00:00,08:00:00,A,1\n"
        "T1,13:00:00,13:05:00,C,2\n"
        "T1,18:00:00,18:00:00,B,3\n"
        "T2,25:00:00,25:00:00,A,1\n"
        "T2,30:00:00,30:00:00,B,2\n", encoding="utf-8")
    (directory / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "S1,1,1,1,1,1,1,1,20260101,20261231\n", encoding="utf-8")


class AirportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "airports.csv"
        self.path.write_text(AIRPORTS_CSV, encoding="utf-8")
        self.airports = load_airports(self.path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_loads_only_entries_with_iata(self):
        self.assertEqual(sorted(self.airports), ["BER", "FCO", "FRA"])
        self.assertEqual(self.airports["BER"]["city"], "Berlin")
        self.assertTrue(self.airports["BER"]["scheduled_service"])

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(lookup("ber", self.airports)["name"], "Berlin Brandenburg")

    def test_search_by_city(self):
        hits = search("rome", self.airports)
        self.assertEqual([h["iata"] for h in hits], ["FCO"])

    def test_distance_ber_fco(self):
        dist = distance_km(52.3667, 13.5033, 41.8003, 12.2389)
        self.assertAlmostEqual(dist, 1187, delta=15)

    def test_nearest_ignores_non_scheduled(self):
        hits = nearest(50.0, 8.5, self.airports, limit=3, max_km=200)
        self.assertEqual(hits[0]["iata"], "FRA")  # der private Platz fliegt raus
        self.assertIn("distance_km", hits[0])

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_airports(Path(self.tmp.name) / "nope.csv")


class GtfsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        _write_gtfs(self.dir)
        self.feed = GtfsFeed(self.dir)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_departures_direct(self):
        out = self.feed.departures("A", "B", date(2026, 11, 5))
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["departure"], "08:00")
        self.assertEqual(out[0]["minutes"], 600)
        self.assertEqual(out[0]["route"], "F1")

    def test_times_after_midnight(self):
        out = self.feed.departures("A", "B", date(2026, 11, 5), after="24:00")
        self.assertEqual([o["departure"] for o in out], ["25:00"])

    def test_wrong_direction_returns_nothing(self):
        self.assertEqual(self.feed.departures("B", "A", date(2026, 11, 5)), [])

    def test_unknown_stop(self):
        self.assertEqual(self.feed.departures("A", "X", date(2026, 11, 5)), [])

    def test_no_price_field(self):
        out = self.feed.departures("A", "B", date(2026, 11, 5))
        self.assertTrue(out)
        for entry in out:
            self.assertNotIn("price", entry)


if __name__ == "__main__":
    unittest.main(verbosity=2)
