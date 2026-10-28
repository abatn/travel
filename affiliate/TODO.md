# TODO: Affiliate-Programme anmelden und Kennungen eintragen

**Status: OFFEN** (Stand 22.10.2026) · Grundlage: `ENTSCHEIDUNG.md` · Code: fertig und getestet,
es fehlen nur die echten Partner-IDs.

Ohne ID funktioniert alles weiter – es wird nur nichts getaggt (keine Provision). Die UI sagt das
ehrlich („Kein Affiliate-Link: … keine ID konfiguriert“).

---

## 0. Für die Anzeige von Flügen/Hotels/Fähren/Kreuzfahrten (Stand 24.10.2026)

Grund: Eigene Preisdaten dürfen wir nicht anzeigen (siehe `docs/QUELLEN_PRUEFUNG.md`).
Lösung: Partner-Widgets/White-Label + Partner-APIs. Dafür fehlen nur die Kennungen.

| # | Kategorie | Firma | Anmeldung | Feldname | Kosten | Status |
|---|---|---|---|---|---|---|
| A | Flüge | **Travelpayouts / Aviasales** | travelpayouts.com → Programm „Aviasales" verbinden | **Marker** (`793886`; Projekt-/trs-ID `589352`) | 0 € (Provision) | ☑ Marker gesetzt, Script integriert; Link-Template offen |
| B | Hotels | **Booking.com** (über Awin oder CJ) | awin.com / cj.com → Booking-Programm | **Publisher-ID** + **Advertiser-ID** (`mid=6776`) | 0 € (Provision) | ☐ offen |
| C | Fähren | **Ferryhopper** | partners.ferryhopper.com → Affiliate/API-Partner | **Affiliate-ID / API-Key** | 0 € (Provision) | ☐ offen |
| D | Fähren (Alt.) | **Direct Ferries Connect** | directferriesconnect.com → „Become a Partner" | **Partner-/Agenten-Zugang** | 0 € (Provision) | ☐ offen |
| E | Kreuzfahrten | **Cruise Itinerary** | cruise-itinerary.com → Developer-Abo | **API-Key** | 149 USD/Monat | ☐ offen |
| F | Flüge (optional) | **Amadeus** | developers.amadeus.com → Production | **Client-ID + Client-Secret** | pay-per-call | ☐ offen |

**Pflicht für Flüge/Hotels/Fähren:** A, B, C. · **Optional:** D (Alternative zu C), E (nur Kreuzfahrten), F (eigene Airline-Daten).

**Travelpayouts (A) – Stand:** Marker `793886` steht in `affiliate/config.yaml` (`partners.travelpayouts.id`);
die Projekt-/`trs`-ID des Emerald-Projekts ist `589352`. Quelle für den Marker: `entrypoint_config`
des Emerald-Servers (Stand 28.10.2026), das Emerald-Script
`https://emrldtp.cc/NTg5MzUy.js?t=589352` liegt im `<head>` von `base.html` und `legal.html`.
Das Backend-`link_template` ist weiterhin leer – Links, die der Server selbst baut, werden dadurch
noch **nicht** mit `marker` getaggt.

### Abnahmekriterien (Definition of Done)

- [ ] Kennungen liegen außerhalb des Repos (z. B. `AFFILIATE_CONFIG=/etc/reise-agent-affiliate.yaml`, Rechte 600); öffentliche Marker (z. B. Travelpayouts `793886`) dürfen im Repo bleiben.
- [ ] Widget/API rendert echte Preise, ohne Platzhalter und ohne erfundene Links.
- [ ] Anzeige ist als „Anzeige" gekennzeichnet; Links mit `rel="sponsored nofollow"`.
- [ ] **Keine** Partner-Preise in unserer Datenbank (Booking/Travelpayouts verbieten Caching).
- [ ] `rights.status: approved` im Registry-Eintrag erst nach erfolgreichem Test.
- [ ] Browser-Konsole ohne Fehler; Seite lädt unter 3 s.

**Nicht liefern:** Passwörter, Konto-E-Mails, Session-Cookies. Nur IDs/Keys.

---

## 1. Programme anmelden (kostenlos, Firmendaten nötig)

Die Provision wird an den **Programm-Account** ausgezahlt – die Anmeldung muss auf deinen Namen /
deine Firma laufen. Keine IDs erfinden, keine fremden Accounts nutzen.

| # | Kategorie | Programm | Anmeldung | ID heißt dort | Status |
|---|---|---|---|---|---|
| 1 | Flüge | **Travelpayouts** (Aviasales/Kiwi) | travelpayouts.com → „Sign up“ | **Marker** (z. B. 123456) | ☐ offen |
| 2 | Hotels | **Awin** (Booking.com/eDreams) | awin.com → „Publisher werden“ | **Publisher-ID** (Zahl, z. B. 987654) + **Advertiser-ID** (`awinmid`) | ☐ offen |
| 3 | Hotels (Alt.) | Booking.com direkt | booking.com/affiliate-program | Affiliate-ID | ☐ offen (nur falls Awin nicht klappt) |
| 4 | Fähren | **Direct Ferries** | directferries.com/affiliate.htm → „Become a Partner“ | **Affiliate-ID** | ☐ offen |
| 5 | Fähren (Alt.) | 12Go | agent.12go.asia | Partner-ID | ☐ offen (Alternative für Asien-Routen) |
| 6 | Kreuzfahrten | **CruiseDirect** (CJ) | cruisedirect.com/affiliates | **SID / Publisher-ID** | ☐ offen |

Die **fett** markierten vier sind die gewählte Kombination (siehe `ENTSCHEIDUNG.md`).

---

## 2. Was geliefert werden muss (pro Programm drei Zeilen)

```
Programm: Travelpayouts
ID/Marker: <deine ID>
Beispiel-Link aus dem Dashboard: <kompletter Link aus dem Link-Generator>
```

* **Nur ID + Beispiel-Link** – kein Passwort, keine Zugangsdaten, keine Konto-E-Mails.
* Aus dem Beispiel-Link baue ich das Link-Template (Platzhalter `{target_encoded}`, `{id}`,
  `{campaign}`) und teste es.

---

## 3. Eintragen in `affiliate/config.yaml`

| Zeile (aktuell) | Feld | Inhalt |
|---|---|---|
| 28 | `awin.id` | Awin-Publisher-ID |
| 32 | `awin.campaign` | Advertiser-ID (`awinmid`, z. B. Booking.com-Programm) |
| 42 | `travelpayouts.id` | Marker |
| 45 | `travelpayouts.link_template` | Template aus dem Dashboard |
| 55 / 58 | `directferries.id` / `.link_template` | dito |
| 68 / 70 | `cruisedirect.id` / `.link_template` | dito |

Beispiel (Awin – Template ist schon korrekt, nur ID + Kampagne fehlen):

```yaml
awin:
  id: "987654"
  campaign: "12345"      # awinmid des Booking.com-Programms
```

---

## 4. Abnahme (nach dem Eintragen)

```bash
# 1. Affiliate-Logik prüfen (ohne echte Anbieter)
python3 affiliate/tests/test_affiliate.py

# 2. UI-Fluss prüfen (Disclosure, rel=sponsored)
python3 ui/tests/e2e_affiliate_test.py

# 3. Echte Links eines Laufs prüfen
python3 affiliate/check_links.py <job_id>
```

Erfolgskriterien:

* `check_links.py` zeigt `Affiliate = ja` und `Erreichbar = ja` für die betroffenen Links.
* In der UI steht **„Anzeige · Affiliate-Link“** direkt über dem Button, `rel="sponsored"` ist gesetzt.
* Die Empfehlung bleibt **unverändert der günstigste Preis** (keine Provision in der Rangfolge).
* Billigflieger-Links (Ryanair/Wizz/easyJet) bleiben ohne Tag – das ist korrekt und gewollt.

---

## 5. Nicht vergessen (rechtlich)

* Disclosure ist eingebaut („Anzeige“, § 5a UWG/§ 6 DDG) – **nicht entfernen**.
* Keine Zahlung, keine Buchungsdatenweitergabe, kein Paket-Gesamtpreis (§§ 651b/651c/651w BGB) –
  `affiliate/legal.py` und `ui_guard()` prüfen das in den Tests.
* Bei einer Prüfung durch die Partner: die Links müssen auf der **eigenen** Domain/Projekt
  eingetragen sein (Travelpayouts/Awin verlangen ein Projekt bzw. eine Website).
