# Affiliate- und Provisionslogik: Recherche, Vergleich, Entscheidung

Stand: 22.10.2026 · Alle Zahlen sind aus den unten genannten Quellen; wo Quellen sich widersprechen,
steht das ausdrücklich dabei. **Es sind keine Affiliate-IDs erfunden** – das System startet ohne
Partner-IDs und sagt das auch (siehe „Ohne ID kein Link“).

---

## 1. Recherche-Ergebnisse

### 1.1 Wie Open-Source-Projekte Affiliate-Links einbetten

| Projekt | Muster | Beleg |
|---|---|---|
| **Voyspark** (MIT, SDK/CLI/MCP) | Jede Antwort enthält Buchungs-URLs **mit eingebettetem Affiliate-Tracking** (Travelpayouts/Aviasales für Flüge, Hotellook für Hotels); die ID steckt serverseitig im Link, der Client sieht nur die fertige URL | voyspark.com/en/developers („Every response includes booking URLs with embedded affiliate tracking“) |
| **Booking.com MCP-Server** (offiziell) | Affiliate-ID **nicht in der URL**, sondern als Header `x-booking-affiliate-id` + Demand-API-Key am MCP-Endpunkt | developers.booking.com/mcp-server/docs/get-started |
| **bobberrisford/affiliatemcp** (MIT) | 86 Netzwerk-Adapter; Referenz ist Awin mit **Link Builder** und Publisher-ID; Trennung Publisher-/Advertiser-Seite | github.com/bobberrisford/affiliatemcp |
| **1Stay / Stayker** | Bewusst **kein** Affiliate: echte Buchung mit Bestätigungsnummer, Monetarisierung über Stripe Connect | github.com/STAYKER-COM/1Stay-mcp |
| **SnapLinker MCP** | Werkzeug zur Affiliate-Link-Erzeugung als MCP-Dienst | mcp.snaplinker.com |

**Abgeleitete Muster:** (a) ID im Query-Parameter oder im Pfad, (b) ID im Header (nur bei
Partner-APIs), (c) Netzwerk-Redirector (`awin1.com/cread.php?…`, `tbs.tradedoubler.com/click?…`),
(d) Link-Builder-API des Netzwerks. Alle Varianten laufen darauf hinaus: **ein Template mit
Platzhaltern für Ziel-URL und ID** – genau das setzen wir um, statt Netzwerk-Interna zu raten.

### 1.2 Provisionen und Cookie-Laufzeiten je Kategorie

| Programm / Netzwerk | Kategorie | Provision | Cookie | Quelle |
|---|---|---|---|---|
| **Booking.com** (eigenes Programm) | Hotel | 4 % | **eine Session** | Travelpayouts-Brandseite; affnext.com |
| **TripAdvisor** | Hotel | 50 % des Werbeumsatzes (effektiv ≈ 2–5 %) | 14 Tage | Travelpayouts; LinkApprove |
| **Agoda** | Hotel | 4–7 % | 30 Tage | LinkApprove; affnext |
| **Hotels.com / Expedia** | Hotel | 4 % / 3 % | 7 Tage | LinkApprove |
| **Travelpayouts** (Netzwerk) | Flug/Hotel | bis 70 % Rev-Share; typ. Flüge 1,1–1,5 %, Hotels 4–5 % | meist 30 Tage | support.travelpayouts.com |
| **Kiwi.com** | Flug | 3 % | 30 Tage | travelpayouts.com/blog |
| **Aviasales** | Flug | 50–70 % des Ertrags | 30 Tage | Travelpayouts-Brandliste |
| **CheapOair** | Flug | 8 USD/Ticket (Travelpayouts) bzw. bis 35 USD/Buchung (Awin) | 30 / 90 Tage | beide Quellen |
| **Skyscanner** | Flug/Hotel | Flüge **keine** Provision, Hotels 20 % | 30 Tage | howtojoinaffiliateprograms.com |
| **Direct Ferries** (offiziell) | Fähre | **50 % der Provision, die DF vom Operator erhält**; über Netzwerke 2 % (CJ) bzw. 4 % (TradeDoubler NL) | 30 Tage | directferries.com/affiliate.htm; trakaff; tradedoubler |
| **12Go** | Fähre/Bus/Bahn | 50 % Rev-Share (Ø ≈ 3 USD/Buchung) | 30 Tage | agent.12go.asia |
| **CruiseDirect** (offiziell) | Kreuzfahrt | 3 % des provisionsfähigen Reisepreises | **45 Tage** | cruisedirect.com/affiliates |
| **Royal Caribbean** (TradeDoubler) | Kreuzfahrt | bis 4 % des Reisepreises (ohne Flüge/Steuern) | 30 Tage (TD) / 45 Tage laut Verzeichnis – **widersprüchlich** | reports.tradedoubler.com; uppromote |
| **Cruisebound** (Impact) | Kreuzfahrt | „höher als Wettbewerber“ (keine Zahl genannt) | 30 Tage | prnewswire.com (02.10.2025) |
| **GoToSea** | Kreuzfahrt | 3 %+ | 45 Tage | gotosea.com/affiliate |

**Branchenkennzahlen (Studie):** Partnerize *Travel Benchmarks Q1 2025*: durchschnittliche
Publisher-Provision **5,7 %**, Average Order Value **458 USD**, Conversion **1,5 %**, ROAS 17,57.
Rakuten Advertising *2025 Travel Affiliate Intelligence Report*: Reiseentscheidungen sind
mehrstufig, Last-Click allein greift zu kurz – lange Cookies sind für die Reiseplanung wichtiger
als die headline-Provision.

### 1.3 Der wichtigste Fallstrick: Billigflieger zahlen nicht

Travelpayouts (offizielle Hilfe, Stand 29.04.2024) listet **Wizzair, Indigo, Jetstar und EasyJet**
als Fluggesellschaften **ohne Provision**; Ryanair kooperiert nicht (kein eigenes Programm; Seiten,
die eines anbieten, sind nicht verifizierbar). Begründung: Billigflieger zahlen grundsätzlich keine
Agentenprovision. **Konsequenz für uns:** Die günstigsten Flüge in unseren Ergebnissen sind
überwiegend Ryanair/Wizz/easyJet – also genau die Tarife **ohne** Provision. Ein System, das
Provision optimiert, würde teurere Flüge empfehlen. Das ist mit der Kernregel „günstigster Preis“
unvereinbar. **Entscheidung: Die Provision darf die Rangfolge nie beeinflussen.**

### 1.4 Rechtslage (Deutschland/EU)

| Norm | Inhalt | Konsequenz |
|---|---|---|
| **§ 651a BGB** | Pauschalreise = mind. zwei Reiseleistungen zu einem **Gesamtpreis** | Ein Gesamtpreis-Angebot mit Buchungsabschluss macht uns zum **Reiseveranstalter** (volle Haftung) |
| **§ 651b BGB** | Abgrenzung: einheitlicher Buchungsvorgang **oder** Gesamtpreis **oder** Bewerbung als „Pauschalreise“ ⇒ Reiseveranstalter; Vermittlerklausel hilft dann nicht | Kein Paket-Checkout, keine Gesamtpreis-Buchung |
| **§ 651w BGB** | **Vermittler verbundener Reiseleistungen**: mind. zwei Leistungen, die der Reisende **getrennt auswählt** und **getrennt bezahlt** bzw. sich getrennt zur Zahlung verpflichtet; Informationspflichten (Art. 251 EGBGB); **Insolvenzsicherung nur, wenn Zahlungen entgegengenommen werden** | Getrennte Buchungs-Buttons je Anbieter, kein Zahlungseingang bei uns ⇒ Vermittler ohne Insolvenzpflicht |
| **§ 651c BGB** | Verbundenes Online-Buchungsverfahren: Weitergabe von Name/Zahlungsdaten/E-Mail innerhalb 24 h ⇒ Pauschalreise | Wir geben **keine** Daten weiter; Buchung passiert beim Anbieter |
| **§ 5a UWG / § 6 DDG** | Affiliate-Links sind Werbung; der kommerzielle Zweck muss **auf den ersten Blick** erkennbar sein | Kennzeichnung „Anzeige/Werbung“ direkt am Link, nicht im Kleingedruckten |
| **LG München I, 09.07.2024 – 1 HK O 12576/23**; **OLG München, 30.10.2025 – 29 U 2633/24** | Ein Hinweis am Textende genügt nicht; auch Teaser müssen gekennzeichnet sein | Disclosure **oberhalb/am** Link, sichtbar vor dem Klick |
| **LG Berlin II, 02.08.2024 – 102 O 27/24** | Ein Einkaufswagen-Symbol allein kennzeichnet keine Provision | Textliche Kennzeichnung, kein reines Icon |

**Damit ist die Grenze klar:** Wir dürfen einen **Preisvergleich** anzeigen (auch eine Summe als
Information), aber **kein Paket zum Gesamtpreis verkaufen**, **keine Zahlung annehmen** und **keine
Buchungsdaten weitergeben**. Genau so ist das System gebaut – die Affiliate-Schicht muss das
bewahren, nicht aufweichen.

---

## 2. Vergleichsmatrix der Optionen

Bewertung 1–5 (5 = beste). „Rechtssicherheit“ = wie gut die Option zur Vermittlerrolle passt.

| Option | Kategorien | Provision | Cookie | Integrationsaufwand | Rechtssicherheit | Summe |
|---|---|---|---|---|---|---|
| **Travelpayouts** (Netzwerk: Aviasales, Kiwi, Hotellook, 12Go) | Flug, Hotel, Fähre | 1,1–5 % (Flüge/Hotels), 50 % Rev-Share bei 12Go | meist 30 Tage | **niedrig** (ein Marker-Parameter `marker=`) | 5 (nur Weiterleitung, kein Verkauf) | **4,5** |
| **Awin** (Netzwerk, z. B. Booking.com, eDreams) | Hotel, Flug | 2–6 % | 30 Tage (Standard) | niedrig–mittel (Link Builder / `cread.php`) | 5 | **4,0** |
| **Booking.com eigenes Programm** | Hotel | 4 % | **eine Session** | mittel (Partnerfreigabe) | 5 | **3,5** (kurze Cookie) |
| **Direct Ferries** (direkt) | Fähre | 50 % der DF-Provision (effektiv 2–4 %) | 30 Tage | mittel (Partnerfreigabe) | 5 | **4,0** |
| **12Go** | Fähre/Transport | 50 % Rev-Share | 30 Tage | niedrig | 5 | **4,0** |
| **CruiseDirect** (CJ) | Kreuzfahrt | 3 % | **45 Tage** | mittel | 5 | **4,5** |
| **Royal Caribbean** (TradeDoubler) | Kreuzfahrt | bis 4 % | 30/45 Tage (unklar) | mittel | 5 | **3,5** |
| **Kiwi.com** (direkt) | Flug | 3 % | 30 Tage | niedrig | 5 | **4,0** |
| **Ryanair / Wizz / easyJet** | Flug | **0 %** | – | – | – | **1,0** (nicht nutzbar) |
| **Skyscanner** | Flug | Flüge 0 %, Hotels 20 % | 30 Tage | niedrig | 5 | **2,0** (für Flüge untauglich) |

**Nicht gewählt:** Ein eigenes Buchungssystem mit Zahlung (Stayker-Muster) – würde Zahlungsabwicklung,
Insolvenzsicherung und ggf. Veranstalterhaftung bedeuten. Das ist ein anderes Geschäftsmodell und
widerspricht der bestehenden Architektur (keine Zahlfunktion).

---

## 3. Entscheidung

**Wir setzen auf ein netzwerk-agnostisches, konfigurationsgetriebenes Link-Modell mit vier
Partnerfamilien:**

1. **Travelpayouts** als Hauptnetz für Flüge (Aviasales/Kiwi) und Hotels (Hotellook) – ein
   `marker`-Parameter, 30 Tage Cookie, dokumentiert, kein Partnerfreigabe-Aufwand pro Marke.
2. **Awin** als Zweitnetz für Hotels (Booking.com, eDreams) – 30 Tage Cookie, `cread.php`-Deep-Link.
3. **Direct Ferries** (direkt) bzw. **12Go** für Fähren – 30 Tage Cookie, 2–4 % bzw. 50 % Rev-Share.
4. **CruiseDirect** (CJ) für Kreuzfahrten – 45 Tage Cookie, 3 % – die längste Cookie-Laufzeit im
   Vergleich, was bei Kreuzfahrt-Buchungsvorlauf (Monate) den Ausschlag gibt.

**Begründung in drei Sätzen:**
* **Abdeckung:** Diese vier decken alle vier Kategorien mit dokumentierten Programmen ab, ohne dass
  wir für jede Marke eine eigene Partnerschaft brauchen.
* **Rechtssicherheit:** Alle vier sind reine Weiterleitungs-Programme (kein Verkauf, keine Zahlung,
  keine Datenweitergabe) – die Vermittlerrolle nach § 651w BGB bleibt unberührt, solange die UI
  getrennte Buchungswege und keine Gesamtpreis-Buchung anbietet.
* **Kein Interessenkonflikt:** Die Provision fließt **nie** in die Rangfolge ein. Wo keine Provision
  möglich ist (Ryanair/Wizz/easyJet – die günstigsten Tarife), bleibt der Link ungetaggt; die UI sagt
  das offen. Ein System, das Provision über Preis stellt, wäre kein Preisvergleich mehr.

### 3.1 „Ohne ID kein Link“ — keine erfundenen Kennungen

> **Offen:** Anmeldung bei den Programmen und Eintragen der IDs – Checkliste in `TODO.md`.

Das Repo enthält **keine** echten Affiliate-IDs. `affiliate/config.yaml` liefert das Schema mit
leeren IDs; solange eine ID fehlt, wird **kein** Affiliate-Link erzeugt (die UI zeigt den normalen
Anbieter-Link ohne Kennzeichnung). Ein `demo: true`-Partner mit offensichtlich fiktiver ID
(`TESTMARKER-0000`) existiert nur für die Tests und wird in der UI als **Testkennung** angezeigt.
Das ist die einzige ehrliche Variante: Eine Provision kann nur derjenige erhalten, der tatsächlich
im Programm angemeldet ist.

### 3.2 Technische Leitplanken

* **Domain-Bindung:** Ein Partner wird nur getaggt, wenn der Zielhost zu seinem `domains`-Eintrag
  passt. Ein Booking.com-Partner kann nie einen Ryanair-Link taggen (Fehlattribution/Fraud).
* **Strukturprüfung:** Nach dem Bau wird geprüft, dass die ID im Link steht und der Host zum Partner
  gehört – sonst `invalid`.
* **Erreichbarkeitsprüfung:** HEAD/GET mit kurzem Timeout, nur für erlaubte Domains, Ergebnis
  gecacht (1 h). Nicht erreichbar ⇒ Link wird **nicht** als Affiliate-Link gezeigt.
* **Doppel-Tagging ausgeschlossen:** Ein bereits getaggter Link wird nicht erneut getaggt.
* **Keine Datenweitergabe:** Der Link enthält nur die ID und die Ziel-URL – keine Nutzer-, Buchungs-
  oder Zahlungsdaten.

### 3.3 Rechtliche Leitplanken in der UI

* Disclosure **direkt am Link** („Anzeige · Affiliate-Link“) und ein Hinweisblock oberhalb der
  Buchungsbuttons; `rel="sponsored noopener"`.
* Klarstellung: **Vertrag kommt ausschließlich mit dem Anbieter zustande**; wir sind
  Vermittler, keine Vertragspartei, wir nehmen **keine Zahlung** entgegen.
* Kein „Paket buchen“: jede Leistung hat ihren eigenen Buchungsweg; die Bündelungssumme ist
  ausdrücklich ein **Vergleichswert**, kein Angebot (§ 651b BGB).
* Keine Weitergabe von Name/Zahlungsdaten an den nächsten Anbieter (§ 651c BGB).

---

## 4. Quellen

* Travelpayouts Help Center: „What is Travelpayouts and how it works“, „How are low-cost airlines
  tickets rewarded?“ (Liste ohne Provision: Wizzair, Indigo, Jetstar, EasyJet, Stand 29.04.2024),
  „Brand“-Seiten (Booking.com 4 % / one session; Kiwi 3 % / 30 Tage; 12Go 50 % / 30 Tage).
* Awin Help: „Understanding cookies in affiliate marketing“ (Cookie-Dauer, Standard 30 Tage),
  „Awin cookie types and attribution hierarchy“, Merchant-Profile (eDreams 2–3 %, 30 Tage).
* Direct Ferries: `directferries.com/affiliate.htm` (50 % der DF-Provision, Zahlung nach Ablegen
  des Schiffs); TradeDoubler-Programmseite (4 %, 30 Tage); trakaff/postaffiliatepro (2 %, 30 Tage).
* 12Go: `agent.12go.asia` (50 % Rev-Share, 30 Tage, Fähren enthalten).
* CruiseDirect: `cruisedirect.com/affiliates` (3 %, 45 Tage). Royal Caribbean: TradeDoubler
  (bis 4 %, 30 Tage). Cruisebound: PRNewswire 02.10.2025 (30 Tage, Impact).
* Partnerize: „Travel Benchmarks Q1 2025“ (Ø 5,7 % Provision, AOV 458 USD, 1,5 % Conversion).
* Rakuten Advertising: „2025 Travel Affiliate Intelligence Report“.
* Gesetze im Internet: §§ 651a, 651b, 651c, 651v, 651w BGB.
* BMJV-Broschüre „Pauschalreiserecht“; IHK-Infoblatt „Reiserecht – Reisevermittler“ (2024);
  Bundeswirtschaftsministerium FAQ Reisebranche.
* LG München I, 09.07.2024 – 1 HK O 12576/23; OLG München, 30.10.2025 – 29 U 2633/24;
  LG Berlin II, 02.08.2024 – 102 O 27/24; Wettbewerbszentrale-Leitfaden Werbekennzeichnung (08/2024).
* GitHub: Voyspark (Affiliate-URLs in jeder Antwort), Booking.com MCP (Affiliate-ID im Header),
  bobberrisford/affiliatemcp (Awin-Referenz, 86 Adapter), 1Stay/Stayker (bewusst kein Affiliate).
