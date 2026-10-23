#!/usr/bin/env python3
"""SEO-Prüfwerkzeug: Meta, JSON-LD, Sitemap, robots.txt und Crawl-Simulation.

Aufruf:
    python3 seo/validate.py [--base http://127.0.0.1:8077]

Prüft (Exitcode 0 = alles in Ordnung):
  * robots.txt: Sitemap-Zeile, Regeln für /jobs/, /api/, /alarms
  * sitemap.xml: valides XML, URLs liefern 200, sind indexierbar und selbst-kanonisch
  * jede indexierbare Seite: Title/Description-Länge, genau eine H1, lang, viewport,
    keine externen Ressourcen (Ladezeit), selbst-kanonisch, robots=index
  * JSON-LD: parsebar, Pflichtfelder je Typ, kein AggregateRating ohne echte Reviews
  * noindex-Seiten: /jobs/<id>, /alarms, /api/*
  * Kompression: gzip für HTML
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET

import requests

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import jsonld as seo_jsonld  # noqa: E402

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
REQUIRED_HEAD = ('<meta charset', 'name="viewport"', '<title>', 'name="description"',
                 'rel="canonical"', 'name="robots"', 'lang="de"')

results: list[tuple[bool, str, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def jsonld_blocks(html: str) -> list:
    out = []
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            out.append(json.loads(raw.replace("<\\/", "</")))
        except Exception as exc:
            out.append({"_parse_error": str(exc)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8077")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    s = requests.Session()

    print("1) robots.txt")
    r = s.get(base + "/robots.txt", timeout=20)
    check(r.status_code == 200, "robots.txt erreichbar", str(r.status_code))
    robots = r.text
    check("Sitemap:" in robots and "sitemap.xml" in robots, "Sitemap-Verweis vorhanden")
    check("Disallow: /jobs/" not in robots,
          "Lauf-Ergebnisseiten NICHT per robots.txt gesperrt (noindex im HTML wirkt sonst nicht)")
    check("Disallow: /static/" not in robots, "CSS/JS nicht gesperrt (Rendering)")
    check("Disallow: /api/" in robots, "API gesperrt")
    check("Disallow: /alarms" in robots, "Alarme gesperrt")
    check("Allow: /fluege" in robots, "Kategorieseiten erlaubt")

    print("\n2) sitemap.xml")
    r = s.get(base + "/sitemap.xml", timeout=20)
    check(r.status_code == 200, "sitemap.xml erreichbar", str(r.status_code))
    check(r.headers.get("content-type", "").startswith("application/xml"),
          "Content-Type application/xml", r.headers.get("content-type", ""))
    urls: list[tuple[str, str | None]] = []
    try:
        root = ET.fromstring(r.content)
        urls = [(u.find("sm:loc", NS).text, (u.find("sm:lastmod", NS).text
                                             if u.find("sm:lastmod", NS) is not None else None))
                for u in root.findall("sm:url", NS)]
        check(True, "XML valide", f"{len(urls)} URLs")
    except Exception as exc:
        check(False, "XML valide", str(exc)[:80])
    check(len(urls) <= 50000, "URL-Anzahl im Limit", str(len(urls)))
    check(all(loc.startswith(base + "/") for loc, _ in urls),
          "alle URLs absolut und auf dieser Domain")

    print("\n3) Crawl-Simulation (Sitemap-URLs)")
    for loc, lastmod in urls:
        r = s.get(loc, timeout=30)
        ok_status = r.status_code == 200
        head = r.text[:4000]
        robots_meta = re.search(r'name="robots" content="([^"]+)"', head)
        indexable = bool(robots_meta and "noindex" not in robots_meta.group(1))
        canon = re.search(r'rel="canonical" href="([^"]+)"', head)
        self_canon = bool(canon and canon.group(1).rstrip("/") == loc.rstrip("/"))
        check(ok_status and indexable and self_canon,
              f"{loc.replace(base, '') or '/'}",
              f"HTTP {r.status_code}, robots={robots_meta.group(1) if robots_meta else 'fehlt'}, "
              f"canonical={'selbst' if self_canon else 'abweichend'}")
        if lastmod:
            check(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod)),
                  f"{loc.replace(base, '')}: lastmod-Format", lastmod)

    print("\n4) Meta und Struktur der indexierbaren Seiten")
    for loc, _ in urls:
        r = s.get(loc, timeout=30)
        html = r.text
        title = re.search(r"<title>(.*?)</title>", html, re.S)
        desc = re.search(r'name="description" content="([^"]*)"', html)
        t = (title.group(1).strip() if title else "")
        d = (desc.group(1).strip() if desc else "")
        check(20 <= len(t) <= 60, f"{loc.replace(base, '')}: Title-Länge", f"{len(t)} Zeichen")
        check(80 <= len(d) <= 160, f"{loc.replace(base, '')}: Description-Länge",
              f"{len(d)} Zeichen")
        h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        check(len(h1s) == 1, f"{loc.replace(base, '')}: genau eine H1", f"{len(h1s)} gefunden")
        check(all(k in html for k in REQUIRED_HEAD), f"{loc.replace(base, '')}: Kopf-Tags vollständig")
        external = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
        own_external = [u for u in external if not u.startswith(base)]
        # Buchungslinks sind erlaubt (externe Anbieter); Ressourcen nicht
        resources = [u for u in own_external
                     if re.search(r"\.(css|js|woff2?|png|jpe?g|svg)(\?|$)", u)]
        check(not resources, f"{loc.replace(base, '')}: keine externen Ressourcen",
              ", ".join(resources[:2]))
        blocks = jsonld_blocks(html)
        check(bool(blocks), f"{loc.replace(base, '')}: JSON-LD vorhanden", f"{len(blocks)} Blöcke")
        problems: list[str] = []
        for b in blocks:
            if "_parse_error" in b:
                problems.append("Parse-Fehler")
            else:
                problems += seo_jsonld.validate(b)
        check(not problems, f"{loc.replace(base, '')}: JSON-LD gültig",
              "; ".join(problems[:3]))

    print("\n5) noindex-Seiten")
    for path, label in (("/alarms", "Alarme"), ("/api/status", "API-Status")):
        r = s.get(base + path, timeout=20)
        if path.startswith("/api"):
            check(r.headers.get("content-type", "").startswith("application/json"),
                  f"{label}: JSON (kein HTML)", r.headers.get("content-type", ""))
        else:
            check("noindex" in r.text, f"{label}: noindex gesetzt")
    r = s.post(base + "/api/search", data={"origin": "BER", "destination": "FCO",
                                          "depart_date": "2026-10-31", "adults": "1",
                                          "currency": "EUR", "categories": "flights",
                                          "timeout_seconds": "30"}, timeout=30)
    if r.status_code == 200:
        job_id = r.json().get("job_id")
        done = False
        import time
        for _ in range(90):
            snap = s.get(f"{base}/api/jobs/{job_id}", timeout=20).json()
            if snap.get("state") == "done":
                done = True
                break
            time.sleep(2)
        page = s.get(f"{base}/jobs/{job_id}", timeout=30)
        check(done and page.status_code == 200, "Lauf-Ergebnisseite erreichbar")
        check("noindex" in page.text, "Lauf-Ergebnisseite: noindex")
        check("Disallow: /jobs/" not in robots,
              "kein Widerspruch robots.txt/noindex bei Lauf-Ergebnisseiten")

    r = s.get(base + "/jobs/gibt-es-nicht", timeout=20)
    check(r.status_code == 404, "unbekannter Lauf: HTTP 404 (kein Soft-404)", str(r.status_code))

    print("\n6) Kompression und Performance")
    r = s.get(base + "/fluege", timeout=20, headers={"Accept-Encoding": "gzip"})
    check(r.headers.get("content-encoding") in ("gzip", "br"),
          "HTML wird komprimiert", str(r.headers.get("content-encoding")))
    check(len(r.content) < 60_000, "Seitengröße < 60 KB (unkomprimiert)",
          f"{len(r.text)} Bytes")
    css = s.get(base + "/static/app.css", timeout=20)
    check("max-age" in css.headers.get("cache-control", ""),
          "statische Dateien mit Cache-Header", css.headers.get("cache-control", ""))

    passed = sum(1 for ok, _, _ in results if ok)
    print("\n" + "=" * 70)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label, detail in results:
        if not ok:
            print(f"  FEHLGESCHLAGEN: {label} [{detail}]")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
