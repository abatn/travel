#!/usr/bin/env python3
"""Meta-Tags je Seite (Title, Description, Canonical, Open Graph, Twitter, Robots).

Regeln (siehe seo/ENTSCHEIDUNG.md):
* Title ~60 Zeichen, Description ~155: **Orientierung**, kein Google-Limit –
  Google kürzt pixelbasiert. Die Tests prüfen nur grobe Grenzen (20–60 / 80–160).
* Jede indexierbare Seite hat genau eine kanonische URL.
* Lauf-Ergebnisseiten (/jobs/<id>), Alarme und API bekommen `noindex`.
* Open-Graph/Twitter dienen der Vorschau in sozialen Netzen – kein Ranking-Faktor,
  aber Standard für geteilte Links.
"""
from __future__ import annotations

SITE_NAME = "Reise-Agent"
LOCALE = "de_DE"

# Zähler für die Tests: erwartete Grenzen
TITLE_MIN, TITLE_MAX = 20, 60
DESC_MIN, DESC_MAX = 80, 160


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())


DEFAULT_IMAGE = "/static/og.png"      # 1200x630, mit Chrome erzeugt


def build(title: str, description: str, path: str, *, base_url: str,
          robots: str = "index,follow", image: str | None = DEFAULT_IMAGE,
          og_type: str = "website", extra: dict | None = None) -> dict:
    """Meta-Datensatz für ein Template bauen."""
    title = _clean(title)
    description = _clean(description)
    base_url = str(base_url).rstrip("/")
    canon = base_url + (path if path.startswith("/") else "/" + path)
    meta = {
        "site_name": SITE_NAME,
        "title": title,
        "description": description,
        "canonical": canon,
        "robots": robots,
        "og_type": og_type,
        "og_title": title,
        "og_description": description,
        "og_url": canon,
        "og_image": (base_url + image) if image and image.startswith("/") else image,
        "og_site_name": SITE_NAME,
        "og_locale": LOCALE,
        "twitter_card": "summary_large_image" if image else "summary",
        "twitter_title": title,
        "twitter_description": description,
        "twitter_image": (base_url + image) if image and image.startswith("/") else image,
        "lang": "de",
    }
    if extra:
        meta.update(extra)
    return meta


def for_job(base_url: str, job_id: str, *, title: str | None = None,
            description: str | None = None) -> dict:
    """Ergebnisseite: nutzerspezifischer Lauf -> nicht indexieren."""
    return build(
        title or "Suchergebnisse – Reise-Agent",
        description or ("Live-Preise für deine Suche: Flüge, Hotels, Fähren "
                        "und Kreuzfahrten im Vergleich."),
        f"/jobs/{job_id}",
        base_url=base_url, robots="noindex,follow",
    )


def for_landing(base_url: str, slug: str, page: dict) -> dict:
    return build(page["title"], page["description"], f"/{slug}", base_url=base_url,
                 og_type="website")


ROUTE_LABELS = {"fluege": "Flüge", "hotels": "Hotels", "faehren": "Fähren",
                "kreuzfahrten": "Kreuzfahrten"}


def short_place(name: str, fallback: str = "") -> str:
    """Kurzer Ortsname für den Title: "Berlin Brandenburg" -> "Berlin".

    Nimmt das erste Wort, außer es ist eine Richtungs-/Zusatzangabe (z. B. "Rome Fiumicino"
    -> "Rome", "Palma de Mallorca" -> "Palma"). Kein Übersetzen, keine Erfindung.
    """
    text = " ".join(str(name or "").split())
    if not text:
        return str(fallback or "")
    first = text.split(" ")[0]
    return first if len(first) >= 3 else text


def _fit(text: str, limit: int) -> str:
    """An Wortgrenzen kürzen statt mitten im Wort abzuschneiden."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" –-:,.")
    return cut or text[:limit]


def for_route(base_url: str, category_slug: str, route: str, origin_name: str,
              destination_name: str, *, title: str | None = None,
              description: str | None = None) -> dict:
    cat = category_slug
    label = ROUTE_LABELS.get(cat, cat)
    o = short_place(origin_name, route.split("-")[0])
    d = short_place(destination_name, route.split("-")[-1])
    title = _fit(title or f"{label} {o} – {d}: Preise vergleichen", TITLE_MAX)
    desc = (description
            or f"Aktuelle Preise für {label} {o} – {d} aus mehreren Quellen: günstigster Tarif, "
               f"Endpreis, Stopps und Quellenlage. Jetzt vergleichen.")
    return build(title, desc, f"/{cat}/{route}", base_url=base_url, og_type="article")


def check_lengths(meta: dict) -> list[str]:
    """Prüft die Längenempfehlungen; gibt Hinweise zurück (für Tests)."""
    notes = []
    if not (TITLE_MIN <= len(meta["title"]) <= TITLE_MAX):
        notes.append(f"Title {len(meta['title'])} Zeichen (empfohlen {TITLE_MIN}-{TITLE_MAX})")
    if not (DESC_MIN <= len(meta["description"]) <= DESC_MAX):
        notes.append(f"Description {len(meta['description'])} Zeichen "
                     f"(empfohlen {DESC_MIN}-{DESC_MAX})")
    return notes
