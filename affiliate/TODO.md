# TODO: Affiliate-Programme anmelden und Kennungen eintragen

**Status: OFFEN** (Stand 22.10.2026) · Grundlage: `ENTSCHEIDUNG.md` · Code: fertig und getestet,
es fehlen nur die echten Partner-IDs.

Ohne ID funktioniert alles weiter – es wird nur nichts getaggt (keine Provision). Die UI sagt das
ehrlich („Kein Affiliate-Link: … keine ID konfiguriert“).

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
