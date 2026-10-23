#!/usr/bin/env python3
"""JSON-LD-Bausteine (Schema.org) für die Oberfläche.

Grundsätze (Begründung in seo/ENTSCHEIDUNG.md):

* **Keine erfundenen Bewertungen.** `AggregateRating`/`Review` werden nur erzeugt,
  wenn echte Bewertungen vorliegen – wir haben keine. Erfundene Sterne verstoßen
  gegen Googles Spam-Richtlinien („Review snippet"-Missbrauch) und sind abmahnfähig.
* **Preise nur, wenn sie auf der Seite sichtbar sind.** `Offer`/`AggregateOffer`
  werden aus genau den Angeboten gebaut, die im HTML stehen.
* **Kein Rich Result ohne indexierbare Seite.** Lauf-Ergebnisseiten sind `noindex`;
  die strukturierten Daten dort sind gültig, werden aber nicht als Snippet erscheinen.
  Indexierbar sind die Kategorie- und Routenseiten.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from pages import CATEGORIES, SITE_NAME

ORG_NAME = SITE_NAME
ORG_URL_PATH = "/"


def _script(obj: dict | list) -> dict:
    return {"@context": "https://schema.org", **obj} if isinstance(obj, dict) else obj


def website(base_url: str) -> dict:
    base = base_url.rstrip("/")
    # S5: SearchAction entfernt - die Sitelinks-Searchbox hat Google am 21.11.2024
    # abgeschafft; das Markup hätte keinen Effekt mehr.
    return _script({
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": base + "/",
        "inLanguage": "de",
    })


def organization(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return _script({
        "@type": "Organization",
        "name": SITE_NAME,
        "url": base + "/",
        "description": ("Preisvergleich für Flüge, Hotels, Fähren und Kreuzfahrten. "
                        "Vermittler, nicht Reiseveranstalter."),
        "knowsLanguage": "de",
    })


def breadcrumb(base_url: str, items: list[tuple[str, str]]) -> dict:
    """items: [(Name, Pfad)] – der letzte Eintrag ist die aktuelle Seite."""
    base = base_url.rstrip("/")
    return _script({
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name,
             "item": base + (path if path.startswith("/") else "/" + path)}
            for i, (name, path) in enumerate(items)
        ],
    })


def faq(items: list[tuple[str, str]]) -> dict | None:
    """FAQPage aus echten Fragen/Antworten (keine Keyword-Duplizierung)."""
    if not items:
        return None
    return _script({
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in items
        ],
    })


def offer_list(base_url: str, page_path: str, offers: list[dict],
               currency: str = "EUR", valid_days: int = 1) -> dict | None:
    """ItemList mit Product/Offer für sichtbare Angebote.

    `offers`: [{name, price, currency, provider, url, all_in, stops}]
    Es werden nur Angebote mit Preis und URL aufgenommen; ohne Angebote -> None.
    """
    base = base_url.rstrip("/")
    valid_until = (date.today() + timedelta(days=valid_days)).isoformat()
    items = []
    for i, o in enumerate(offers, start=1):
        price = o.get("price")
        if price is None:
            continue
        name = o.get("name") or o.get("provider") or "Angebot"
        item = {
            "@type": "Product",
            "name": f"{name} – {o.get('route') or 'Reise'}",
            "category": o.get("category") or "Reise",
        }
        if o.get("provider"):
            item["brand"] = {"@type": "Brand", "name": o["provider"]}
        # S4: kein erfundenes availability / priceValidUntil - beides steht so in
        # keiner Quelle. Der Preis ist der sichtbare Preis, sonst nichts.
        offer = {
            "@type": "Offer",
            "price": round(float(price), 2),
            "priceCurrency": (o.get("currency") or currency).upper(),
        }
        if o.get("url"):
            offer["url"] = o["url"]
        if o.get("seller"):
            offer["seller"] = {"@type": "Organization", "name": o["seller"]}
        item["offers"] = offer
        items.append({"@type": "ListItem", "position": i, "item": item})
    if not items:
        return None
    return _script({
        "@type": "ItemList",
        "name": f"Angebote auf {page_path}",
        "numberOfItems": len(items),
        "itemListElement": items,
    })


def aggregate_offer(base_url: str, page_path: str, offers: list[dict],
                    currency: str = "EUR", valid_days: int = 1) -> dict | None:
    """AggregateOffer für eine Preisspanne (nur wenn ≥ 1 Preis vorhanden)."""
    # S4: nur Angebote derselben Währung aggregieren (sonst mischt die Spanne Währungen)
    target = currency.upper()
    prices = [float(o["price"]) for o in offers
              if o.get("price") is not None
              and (o.get("currency") or target).upper() == target]
    if not prices:
        return None
    base = base_url.rstrip("/")
    return _script({
        "@type": "Product",
        "name": f"Reisepreise auf {page_path}",
        "offers": {
            "@type": "AggregateOffer",
            "lowPrice": round(min(prices), 2),
            "highPrice": round(max(prices), 2),
            "priceCurrency": target,
            "offerCount": len(prices),
            "url": base + page_path,
        },
    })


def product_with_rating(base_url: str, name: str, price: float, currency: str,
                        rating_value: float, review_count: int,
                        url: str | None = None) -> dict:
    """NUR verwenden, wenn echte Bewertungen vorliegen.

    Diese Funktion existiert, damit die Regel dokumentiert und testbar ist; sie
    wird in der Oberfläche bewusst nicht aufgerufen (keine Bewertungsquelle).
    """
    return _script({
        "@type": "Product",
        "name": name,
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": rating_value,
            "reviewCount": review_count,
        },
        "offers": {"@type": "Offer", "price": round(float(price), 2),
                   "priceCurrency": currency.upper(),
                   **({"url": (base_url.rstrip("/") + url)} if url else {})},
    })


def to_script_tag(obj: dict | list | None) -> str:
    """JSON-LD als `<script type="application/ld+json">` (escaped, XSS-sicher)."""
    if not obj:
        return ""
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


# ------------------------------------------------------------------ Validierung
REQUIRED = {
    "WebSite": ("name", "url"),
    "Organization": ("name", "url"),
    "BreadcrumbList": ("itemListElement",),
    "FAQPage": ("mainEntity",),
    "ItemList": ("itemListElement",),
    "Product": ("name", "offers"),
    "Offer": ("price", "priceCurrency"),
    "AggregateOffer": ("lowPrice", "priceCurrency", "offerCount"),
}


def validate(obj) -> list[str]:
    """Prüft JSON-LD gegen die Google-Pflichtfelder (vereinfacht). Gibt Fehler zurück."""
    problems: list[str] = []
    items = obj if isinstance(obj, list) else [obj]
    for entry in items:
        if not isinstance(entry, dict):
            problems.append("Eintrag ist kein Objekt")
            continue
        if entry.get("@context") != "https://schema.org":
            problems.append("fehlender @context")
        _walk(entry, problems)
    return problems


def _walk(node, problems: list[str]) -> None:
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str) and t in REQUIRED:
            for field in REQUIRED[t]:
                if field not in node or node[field] in (None, "", []):
                    problems.append(f"{t}: Pflichtfeld '{field}' fehlt")
            if t in ("Offer", "AggregateOffer"):
                price = node.get("price", node.get("lowPrice"))
                try:
                    if float(price) <= 0:
                        problems.append(f"{t}: Preis muss > 0 sein")
                except Exception:
                    problems.append(f"{t}: Preis ist keine Zahl")
            if t == "Product" and "aggregateRating" in node:
                ar = node["aggregateRating"] or {}
                if not ar.get("reviewCount") and not ar.get("ratingCount"):
                    problems.append("Product: aggregateRating ohne reviewCount (unzulässig)")
        for v in node.values():
            _walk(v, problems)
    elif isinstance(node, list):
        for v in node:
            _walk(v, problems)
