#!/usr/bin/env python3
"""Tests der SEO-Schicht (ohne laufenden Server, mit TestClient).

Aufruf: python3 seo/tests/test_seo.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SEO = os.path.dirname(HERE)
ROOT = os.path.dirname(SEO)
sys.path.insert(0, SEO)
sys.path.insert(0, os.path.join(ROOT, "ui"))

import jsonld as seo_jsonld  # noqa: E402
import meta as seo_meta  # noqa: E402
import pages as seo_pages  # noqa: E402
import routes_cache  # noqa: E402
import sitemap as seo_sitemap  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def main() -> int:
    base = "https://example.org"

    print("1) Meta-Tags")
    for slug, page in seo_pages.CATEGORIES.items():
        meta = seo_meta.for_landing(base, slug, page)
        notes = seo_meta.check_lengths(meta)
        check(not notes, f"/{slug}: Title/Description in den Grenzen", "; ".join(notes))
        check(meta["canonical"] == f"{base}/{slug}", f"/{slug}: kanonische URL")
        check(meta["robots"] == "index,follow", f"/{slug}: indexierbar")
        check(meta["lang"] == "de", f"/{slug}: lang=de")
    job_meta = seo_meta.for_job(base, "abc123")
    check("noindex" in job_meta["robots"], "Ergebnisseite: noindex")

    print("\n2) JSON-LD")
    good = seo_jsonld.website(base)
    check(seo_jsonld.validate(good) == [], "WebSite gültig")
    broken = {"@context": "https://schema.org", "@type": "Product", "name": "X"}
    check(seo_jsonld.validate(broken), "Product ohne offers wird erkannt")
    offer = seo_jsonld.offer_list(base, "/fluege", [
        {"name": "Ryanair", "price": 27.99, "currency": "EUR", "provider": "Ryanair",
         "url": "https://example.com/x", "route": "BER – FCO"}])
    check(seo_jsonld.validate(offer) == [], "ItemList mit Offer gültig")
    check(offer["itemListElement"][0]["item"]["offers"]["price"] == 27.99,
          "Preis wird unverändert übernommen")
    agg = seo_jsonld.aggregate_offer(base, "/fluege", [
        {"price": 27.99}, {"price": 88.0}])
    o = agg["offers"]
    check(o["lowPrice"] == 27.99 and o["highPrice"] == 88.0 and o["offerCount"] == 2,
          "AggregateOffer: Spanne und Anzahl korrekt")
    check("priceValidUntil" not in o and "availability" not in o,
          "keine erfundenen Felder (priceValidUntil/availability) im Angebot")
    check(seo_jsonld.offer_list(base, "/x", [{"price": None}]) is None,
          "Angebote ohne Preis werden nicht ausgegeben")
    check("aggregateRating" not in json.dumps(offer) and
          "aggregateRating" not in json.dumps(agg),
          "keine erfundenen Bewertungen (kein AggregateRating)")
    fake_rating = seo_jsonld.product_with_rating(base, "X", 10, "EUR", 4.5, 0)
    check(any("reviewCount" in p for p in seo_jsonld.validate(fake_rating)),
          "AggregateRating ohne reviewCount wird als ungültig erkannt")
    faq = seo_jsonld.faq(seo_pages.CATEGORIES["fluege"]["faq"])
    check(seo_jsonld.validate(faq) == [], "FAQPage gültig")
    tag = seo_jsonld.to_script_tag({"@context": "https://schema.org", "@type": "Thing",
                                    "name": "a</script>b"})
    payload = tag.split(">", 1)[1].rsplit("</script>", 1)[0]
    check("</script>" not in payload and "<\\/script" in payload,
          "JSON-LD escaped (kein Script-Abbruch)")

    print("\n3) Sitemap und robots.txt")
    xml = seo_sitemap.build(base)
    ET.register_namespace("", seo_sitemap.NS)
    root = ET.fromstring(xml.replace('<?xml version="1.0" encoding="UTF-8"?>\n', ""))
    locs = [e.text for e in root.iter(f"{{{seo_sitemap.NS}}}loc")]
    check(root.tag.endswith("urlset"), "Wurzelelement urlset")
    check(f"{base}/" in locs, "Startseite in der Sitemap")
    check(f"{base}/preisvergleich" in locs, "Preisvergleich in der Sitemap")
    for slug in seo_pages.CATEGORIES:
        check(f"{base}/{slug}" in locs, f"/{slug} in der Sitemap")
    check(len(locs) == len(set(locs)), "keine doppelten URLs")
    robots = seo_sitemap.robots(base)
    check(f"Sitemap: {base}/sitemap.xml" in robots, "robots.txt nennt die Sitemap")
    check("Disallow: /jobs/" not in robots,
          "jobs NICHT per robots.txt gesperrt (noindex im HTML wirkt sonst nicht)")
    check("Disallow: /api/" in robots, "API per robots.txt gesperrt")
    check("Disallow: /static/" not in robots, "CSS/JS nicht gesperrt (Rendering)")
    check("Allow: /fluege" in robots, "robots.txt erlaubt Kategorieseiten")

    print("\n4) Routen-Cache")
    tmp = tempfile.mkdtemp(prefix="routes-")
    old_dir = routes_cache.CACHE_DIR
    routes_cache.CACHE_DIR = tmp
    try:
        # Qualitätsgate: mindestens 5 Angebote mit Preis
        offers = [{"price": 27.99 + i, "currency": "EUR", "provider": "Ryanair",
                   "booking_url": "https://example.com/book", "source": "trvl_flights"}
                  for i in range(6)]
        offers.append({"price": None, "currency": "EUR"})
        path = routes_cache.save("flights", "BER", "FCO", offers)
        check(bool(path), "Route gespeichert")
        data = routes_cache.load("flights", "BER-FCO")
        check(data and len(data["offers"]) == 6, "nur Angebote mit Preis gespeichert")
        check(routes_cache.route_id("Berlin", "Rom") == "BERLIN-ROM",
              "Routen-ID normalisiert", routes_cache.route_id("Berlin", "Rom"))
        evil = routes_cache.route_id("../../etc", "passwd")
        check("/" not in evil and ".." not in evil, "kein Pfad-Ausbruch über die Route", evil)
        check(len(routes_cache.list_routes("flights")) == 1, "Routenliste enthält die Route")
        thin = routes_cache.save("flights", "AAA", "BBB", [{"price": 10, "currency": "EUR"}] * 2)
        check(thin is None, "Qualitätsgate: < 5 Angebote werden nicht gespeichert")
    finally:
        routes_cache.CACHE_DIR = old_dir

    print("\n5) HTTP (TestClient)")
    try:
        from fastapi.testclient import TestClient
        import app as ui_app
        client = TestClient(ui_app.app)
        for path in ("/", "/preisvergleich", "/fluege", "/hotels", "/faehren",
                     "/kreuzfahrten", "/sitemap.xml", "/robots.txt"):
            r = client.get(path)
            check(r.status_code == 200, f"GET {path}", str(r.status_code))
        page = client.get("/fluege").text
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
        parsed = [json.loads(b.replace("<\\/", "</")) for b in blocks]
        check(bool(parsed), "Landingpage liefert JSON-LD", f"{len(parsed)} Blöcke")
        check(all(seo_jsonld.validate(p) == [] for p in parsed), "alle Blöcke gültig")
        check(len(re.findall(r"<h1[^>]*>", page)) == 1, "genau eine H1")
        check('name="viewport"' in page, "Viewport gesetzt")
        r = client.get("/jobs/unbekannt")
        check("noindex" in r.text, "unbekannter Lauf: noindex")
        r = client.get("/fluege/../../etc/passwd")
        check(r.status_code in (400, 404), "Pfad-Ausbruch wird abgewiesen", str(r.status_code))
        r = client.get("/sitemap.xml")
        check("urlset" in r.text, "Sitemap über HTTP")
    except Exception as exc:                       # pragma: no cover
        check(False, "TestClient-Prüfungen", str(exc)[:200])

    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 60)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
