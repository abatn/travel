# Affiliate-Schicht

Vollständige Recherche und Begründung: **`ENTSCHEIDUNG.md`**. Kurzfassung:

* **Vier Partnerfamilien** decken alle Kategorien ab: Travelpayouts (Flüge/Hotels),
  Awin (Hotels), Direct Ferries bzw. 12Go (Fähren), CruiseDirect (Kreuzfahrten).
* **Keine Provision ohne Partner:** Billigflieger (Ryanair, Wizz, easyJet) zahlen keine
  Provision – deren Links bleiben ungetaggt, die Empfehlung bleibt der günstigste Preis.
* **Keine erfundenen IDs:** `config.yaml` startet ohne IDs; ohne ID wird kein Affiliate-Link
  erzeugt und die UI sagt das.
* **Kennzeichnung:** „Anzeige · Affiliate-Link“ direkt am Link, `rel="sponsored"`, plus
  Rechtshinweis (Vermittler, kein Veranstalter, keine Zahlung, kein Gesamtpreis-Angebot).
* **Prüfung vor Anzeige:** Struktur (ID im Link, Domain passt) + Erreichbarkeit (HEAD/GET,
  6 s Timeout, Cache 1 h, nur freigegebene Hosts).

## Dateien

```
affiliate/
  ENTSCHEIDUNG.md      Recherche, Vergleichsmatrix, Entscheidung, Quellen
  config.yaml          Partner (IDs leer) + Domain-Zuordnung; Demo-Partner deaktiviert
  builder.py           Link bauen + Strukturprüfung (Domain-Bindung, kein Doppeltagging)
  verify.py            Erreichbarkeitsprüfung mit Cache und Host-Allowlist
  legal.py             Disclosure-, Rechts- und Bündelungstexte + UI-Leitplanken
  check_links.py       CLI: alle Buchungslinks eines Laufs prüfen
  tests/               Unit-Tests + Testkonfigurationen (fiktive Kennung)
  state/               Prüf-Cache (Laufzeit)
```

## Offene Aufgabe

Die Programme sind recherchiert und im Code vorbereitet, aber **noch nicht angemeldet** –
die Schritt-für-Schritt-Liste steht in **`TODO.md`** (Status: offen).

## Aktivieren

1. Beim Partnerprogramm anmelden und im Dashboard die Publisher-/Marker-ID und den
   **Link-Generator** (Template) holen.
2. In `config.yaml` beim jeweiligen Partner `id`, ggf. `campaign` und `link_template` eintragen.
3. Prüfen: `python3 affiliate/check_links.py <job_id>` – zeigt je Link, ob er getaggt und
   erreichbar ist.

Ohne Schritt 1–2 bleibt das System vollständig funktionsfähig – es zeigt dann normale
Anbieter-Links ohne Kennzeichnung und ohne Provision.

## Tests

```bash
python3 affiliate/tests/test_affiliate.py     # 26 Prüfungen (Builder, Prüfung, Rechtstexte)
python3 ui/tests/e2e_affiliate_test.py        # 15 Prüfungen (UI-Fluss, Disclosure, rel=sponsored)
```
