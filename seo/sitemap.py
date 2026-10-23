#!/usr/bin/env python3
"""sitemap.xml und robots.txt – dynamisch aus dem Seitenregister erzeugt.

Regeln (Google Search Central):
* Nur kanonische, indexierbare URLs (200, kein `noindex`, keine Weiterleitung).
* `<lastmod>` nur, wenn bekannt (sonst weglassen statt raten).
* Maximal 50 000 URLs / 50 MB pro Datei – hier weit darunter.
* Sitemap wird in der robots.txt mit absoluter URL genannt.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from pages import CATEGORIES, OVERVIEW_SLUG, SITE_NAME
import routes_cache

NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
STALE_ROUTE_HOURS = 7 * 24        # Routen älter als 7 Tage fliegen aus der Sitemap

# Kategorie-Schlüssel -> Landing-Slug
CATEGORY_SLUG = {v["key"]: slug for slug, v in CATEGORIES.items()}


def _url_entry(parent, loc: str, lastmod: str | None = None,
               changefreq: str | None = None, priority: str | None = None) -> None:
    url = ET.SubElement(parent, f"{{{NS}}}url")
    ET.SubElement(url, f"{{{NS}}}loc").text = loc
    if lastmod:
        ET.SubElement(url, f"{{{NS}}}lastmod").text = lastmod
    if changefreq:
        ET.SubElement(url, f"{{{NS}}}changefreq").text = changefreq
    if priority:
        ET.SubElement(url, f"{{{NS}}}priority").text = priority


def build(base_url: str) -> str:
    """Sitemap als XML-String."""
    base = base_url.rstrip("/")
    ET.register_namespace("", NS)          # Standard-Namespace (kein ns0:-Praefix)
    root = ET.Element(f"{{{NS}}}urlset")

    _url_entry(root, base + "/", priority="1.0", changefreq="daily")
    _url_entry(root, base + f"/{OVERVIEW_SLUG}", priority="0.9", changefreq="weekly")
    for slug in CATEGORIES:
        _url_entry(root, base + f"/{slug}", priority="0.9", changefreq="daily")

    # Routenseiten nur mit echtem, nicht zu altem Inhalt (zwischengespeicherte Angebote)
    for data in routes_cache.all_routes():
        slug = CATEGORY_SLUG.get(data.get("category"))
        route = data.get("_route")
        if not slug or not route:
            continue
        age = routes_cache.age_hours(data)
        if age is None or age > STALE_ROUTE_HOURS // 24 * 24:
            continue          # zu alt: nicht in die Sitemap (vermeidet veraltete Preise)
        lastmod = (data.get("generated_at") or "")[:10] or None
        _url_entry(root, f"{base}/{slug}/{route.lower()}", lastmod=lastmod)

    ET.indent(root, space="  ")
    xml = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml + "\n"


def robots(base_url: str) -> str:
    """robots.txt: öffentliche Seiten erlauben, private/technische sperren."""
    base = base_url.rstrip("/")
    lines = [
        "User-agent: *",
        "Allow: /$",
    ]
    for slug in CATEGORIES:
        lines.append(f"Allow: /{slug}")
    lines.append(f"Allow: /{OVERVIEW_SLUG}")
    lines += [
        "",
        "# WICHTIG: /jobs/ wird NICHT gesperrt, sondern per <meta name=robots noindex>",
        "# im HTML ausgeschlossen. Disallow + noindex zusammen ist ein Widerspruch:",
        "# Google kann das noindex dann nicht lesen (URL-only-Indexierung).",
        "",
        "# Private Bereiche (werden nie verlinkt, kein Index-Interesse)",
        "Disallow: /alarms",
        "# API und Gesundheitscheck",
        "Disallow: /api/",
        "Disallow: /health",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ]
    return "\n".join(lines)


def write_static(directory: str, base_url: str) -> list[str]:
    """Sitemap/robots als Dateien schreiben (für statisches Hosting)."""
    os.makedirs(directory, exist_ok=True)
    sitemap_path = os.path.join(directory, "sitemap.xml")
    robots_path = os.path.join(directory, "robots.txt")
    with open(sitemap_path, "w", encoding="utf-8") as fh:
        fh.write(build(base_url))
    with open(robots_path, "w", encoding="utf-8") as fh:
        fh.write(robots(base_url))
    return [sitemap_path, robots_path]
