#!/usr/bin/env python3
"""SEO-Seitenregister: dauerhafte, indexierbare Seiten der Oberfläche.

Bewusste Entscheidung (siehe seo/ENTSCHEIDUNG.md):

* **Indexiert** werden nur dauerhafte Seiten mit eigenem Inhalt: Startseite,
  Preisvergleichs-Übersicht, die vier Kategorie-Landingpages und – sofern ein
  letzter Suchlauf zwischengespeichert ist – Routenseiten wie /fluege/ber-fco.
* **Nicht indexiert** werden Ergebnisseiten mit Lauf-ID (/jobs/<id>), Alarme
  (privat) und die API. Diese Seiten sind nutzerspezifisch bzw. Duplikate und
  würden als „thin content" gewertet.
"""
from __future__ import annotations

SITE_NAME = "Reise-Agent"
SITE_TAGLINE = "Live-Preisvergleich für Flüge, Hotels, Fähren und Kreuzfahrten"

# Kategorie-Landingpages: slug -> Inhalt
CATEGORIES = {
    "fluege": {
        "key": "flights",
        "title": "Günstige Flüge vergleichen – Live-Preise von 9 Quellen",
        "h1": "Günstige Flüge vergleichen",
        "description": ("Flugpreise live aus 9 Quellen vergleichen: Endpreis inklusive Gepäck, "
                        "Stopps, Airlines und Buchungslink. Ohne Anmeldung, ohne Aufschlag."),
        "intro": ("Wir fragen mehrere Flugquellen gleichzeitig ab und zeigen den günstigsten Tarif "
                  "mit Endpreis. Steuern und Gepäck werden – soweit die Quelle sie ausweist – "
                  "getrennt genannt. Was eine Quelle nicht belegt, steht als „nicht verfügbar“ da."),
        "faq": [
            ("Ist der angezeigte Preis der Endpreis?",
             "Nur wenn die Quelle ihn ausweist. Für viele Tarife nennen wir zusätzlich den Endpreis "
             "inklusive Hand- und Aufgabegepäck; fehlt die Angabe, steht ausdrücklich „nicht verfügbar“."),
            ("Warum fehlen manche Airlines?",
             "Weil eine Quelle sie nicht liefert oder gerade gesperrt ist (Rate-Limit). Die "
             "Quellenübersicht zeigt, welche Quellen antworten und welche pausieren."),
            ("Wie oft werden die Preise aktualisiert?",
             "Bei jeder Suche live. Die angezeigten Preise gelten für den Moment der Abfrage; "
             "verbindlich ist der Preis beim Anbieter."),
        ],
        "presets": {"categories": ["flights"]},
    },
    "hotels": {
        "key": "hotels",
        "title": "Hotels vergleichen – Preise je Nacht mit Steuerstatus",
        "h1": "Hotels vergleichen",
        "description": ("Hotelpreise je Nacht aus mehreren Quellen, mit Sternen, Entfernung zum "
                        "Flughafen und Steuerstatus aus den Detailraten."),
        "intro": ("Hotelpreise sind je Nacht und Zimmer angegeben. Ob Steuern und Gebühren enthalten "
                  "sind, lesen wir aus den Detailraten der Quelle – fehlt der Beleg, steht das dabei. "
                  "Die Entfernung zum Flughafen wird aus Koordinaten berechnet (Haversine), nicht geschätzt."),
        "faq": [
            ("Sind die Hotelpreise pro Nacht oder pro Aufenthalt?",
             "Pro Nacht und Zimmer, sofern die Quelle es so ausweist. Der Gesamtpreis für den "
             "Aufenthalt wird aus Nächten × Nachtpreis berechnet und getrennt angezeigt."),
            ("Sind Steuern enthalten?",
             "Das steht bei jedem Angebot: enthalten, nicht enthalten oder nicht belegt. "
             "Kurort-/City-Tax unterscheidet sich je Stadt und wird, wenn bekannt, genannt."),
        ],
        "presets": {"categories": ["hotels"]},
    },
    "faehren": {
        "key": "ferries",
        "title": "Fähren vergleichen – Preise je Person und Strecke",
        "h1": "Fähren vergleichen",
        "description": ("Fährpreise je Person für Strecken wie Barcelona–Palma oder Helsinki–Tallinn, "
                        "mit Abfahrtszeiten und Kabinen-/Sitzklassen."),
        "intro": ("Fähren unterscheiden sich in der Preisbasis: Sitzplatz je Person, Kabine je Kabine. "
                  "Wir zeigen die günstigste Klasse und weisen aus, worauf sich der Preis bezieht."),
        "faq": [
            ("Gilt der Preis pro Person oder pro Fahrzeug?",
             "Beides ist möglich. Wir weisen die Preisbasis je Angebot aus (je Person oder je Kabine/Fahrzeug)."),
            ("Kann ich ein Auto mitnehmen?",
             "Viele Fährgesellschaften bieten das an; ob ein Fahrzeug im angezeigten Preis enthalten ist, "
             "steht in den Bedingungen der Quelle."),
        ],
        "presets": {"categories": ["ferries"]},
    },
    "kreuzfahrten": {
        "key": "cruises",
        "title": "Kreuzfahrten vergleichen – Preise je Person inkl. Steuern",
        "h1": "Kreuzfahrten vergleichen",
        "description": ("Kreuzfahrtpreise je Person, inklusive Steuern und Gebühren, mit Nächten, "
                        "Einschiffungshafen und Buchungslink."),
        "intro": ("Kreuzfahrtpreise gelten je Person für die ganze Reise. Wir nennen Nächte, "
                  "Einschiffungshafen und ob Steuern enthalten sind; Getränke und Ausflüge sind "
                  "in der Regel nicht enthalten."),
        "faq": [
            ("Was ist im Kreuzfahrtpreis enthalten?",
             "Kabine und Verpflegung an Bord, meist inklusive Steuern und Gebühren. Getränkepakete, "
             "Ausflüge und Trinkgelder sind üblicherweise extra – die Quelle weist es aus."),
            ("Warum sind manche Preise in USD?",
             "Weil die Reederei in USD abrechnet. Wir rechnen nur mit einem belegten Wechselkurs um "
             "und kennzeichnen das; sonst zeigen wir den Originalpreis."),
        ],
        "presets": {"categories": ["cruises"]},
    },
}

OVERVIEW_SLUG = "preisvergleich"
OVERVIEW_TITLE = "Reise-Preisvergleich: Flüge, Hotels, Fähren, Kreuzfahrten"
OVERVIEW_DESCRIPTION = ("Live-Preise aus über 20 Quellen vergleichen: Flüge, Hotels, Fähren und "
                        "Kreuzfahrten. Mit Endpreis, Steuerstatus, Quellenlage und Buchungslink.")

# Seiten, die niemals indexiert werden
NOINDEX_PREFIXES = ("/api/", "/jobs/", "/alarms", "/health")

# Seiten der Sitemap (ohne Routenseiten)
STATIC_PATHS = ["/", f"/{OVERVIEW_SLUG}"] + [f"/{s}" for s in CATEGORIES]
