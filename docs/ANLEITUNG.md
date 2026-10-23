# Das Reise-Agent-System – vollständige Erklärung

Stand 21.10.2026 · Alle Zahlen in diesem Text stammen aus echten Läufen des Systems.

---

## 1. Wofür das System da ist

Ein Reisewunsch wie „Flug von Berlin nach Rom, 2 Personen, ein zentrales Hotel“ ist für sich genommen fast wertlos:
Es gibt Dutzende Sites und Dienste, die dafür Preise anzeigen, aber sie widersprechen einander, rechnen
unterschiedliche Währungen, einmal pro Person und einmal pro Reise, lassen Steuern und Gepäck mal drin und mal
nicht, und sind ständig blockiert (Rate-Limits, Bot-Schutz, Serverausfälle).

Das System besteht aus **drei Erweiterungen** und einem **Prüfrahmen**, der die ganze Arbeit immer wiederholt:

| Erweiterung | Die eine Frage, die sie beantwortet |
|---|---|
| **1 · Dynamische API-Abdeckung** | „Was kostet es wirklich – wenn man **alle** verfügbaren Quellen gleichzeitig fragt?“ |
| **2 · Intelligente Kombination** | „Günstiger: ein Paket aus Flug und Hotel – oder alles einzeln buchen?“ |
| **3 · Preis-Alarm** | „Wann endlich sinkt der Preis unter mein Budget oder auf ein neues Tief?“ |
| **Prüfrahmen (Schleife)** | „Ist das Ergebnis nachweislich gut – und wenn nicht: was muss die nächste Runde besser machen?“ |

Die Grundregel des ganzen Systems: **nichts wird behauptet, was nicht aus einer echten Werkzeugantwort
stammt.** Kein Preis wird geschätzt, keine Steuer wird unterstellt, keine Quelle wird als „dürfte ungefähr so
sein“ zitiert. Was nicht belegbar ist, wird als *nicht verfügbar* ausgewiesen – und manchmal als Grenze offengelegt.

---

## 2. Die Landkarte (welche Datei was macht)

| Datei | Rolle in einem Satz |
|---|---|
| `providers/registry.yaml` | Das **Adressbuch** aller Preisquellen: welche es gibt, wie man sie anspricht, wo in der Antwort der Preis steht. |
| `providers/runner.py` | Der **Einkäufer**: fragt alle Quellen gleichzeitig, sortiert die Antworten in ein gemeinsames Format, sucht das günstigste Angebot. |
| `providers/normalize.py` | Der **Übersetzer**: bringt acht verschiedene Antwortformate auf dieselben Felder (Preis, Währung, Endpreis, Stopps, Koordinaten, Link). |
| `providers/mcp_stdio.py` / `mcp_http.py` | Die **Verbindungsstücke** zu den Quellen (die einen über die Standardein-/ausgabe, die anderen über das Web-Protokoll). |
| `bundling/compare.py` | Der **Bündelrechner**: rechnet Paket, Rundflug+Hotel und Gabelflug+Hotel gegeneinander. |
| `bundling/evidence.json` | Die **Belege** aus der Recherche (19 Einträge mit wörtlichem Zitat, plus Gegenbelege). |
| `alerts/watcher.py` | Der **Wächter**: misst über Stunden und Tage den Preis, feuert einen Alarm nur bei Regelerfüllung. |
| `alerts/alert_config.example.yaml` | Die **Wächter-Einstellungen**: Budget, Tiefpunkt-Regel, Beobachtungsfenster, Cooldown, Scheduler. |
| `harness/loop.sh` | Die **Schleife**: Runde für Runde, bis dreimal gut genug geprüft wurde. |
| `harness/current.md` | Das **Aufgabenheft** für den ausführenden Agenten (enthält keine festen Reiseziele, nur Regeln). |
| `harness/evaluator.md` | Das **Prüfheft**: fünf Kriterien und sechs Deckel, die eine Note verhindern. |
| `harness/proposer.md` | Das **Verbesserungsheft**: darf nur Regeln ergänzen, niemals Ergebnisse übernehmen. |
| `demo.sh` | Die **Vorführung** aller drei Erweiterungen in einem Durchlauf. |

---

## 3. Erweiterung 1 – Dynamische API-Abdeckung

### 3.1 Das Adressbuch

Jede Preisquelle ist ein Eintrag in `registry.yaml`. Ein Eintrag beantwortet vier Fragen:

1. **Wie rufe ich sie an?** (Standard-Ein-/Ausgabe, Web-Protokoll oder direkte Web-Schnittstelle)
2. **Welche Werte muss ich übergeben?** (Platzhalter wie „Abflugort“, „Rückflugdatum“, „Anzahl Personen“, „Währung“)
3. **Wo in der Antwort stehen Preis, Währung, Stopps, Koordinaten?** (Pfade wie „result.flights“)
4. **Ist die Zahl pro Person, pro Reise oder pro Nacht?** – und: weiß ich das überhaupt?

Der entscheidende Punkt: **Eine neue Quelle hinzuzufügen ist ein Textblock in dieser Datei.** Kein Programmcode,
kein Testlauf, kein Neustart. Wer eine neue Quelle kennt, trägt sie ein, und ab da nimmt sie automatisch an allen
Abfragen teil.

Aktuell sind **16 Quellen eingetragen, 15 davon aktiv** – neun für Flüge, sechs für Hotels. Die Recherche dahinter
prüfte **33 Kandidaten** mit echten Aufrufen: 20 funktionierten, 6 lieferten Fehler, 7 waren blockiert
(wörtliche Beispiele: „HTTP 401 – MCP tool calls require an Ignav account“, „Set SERP_API_KEY to your SerpApi key“,
„'apikey' header is required“).

### 3.2 Was beim Abruf passiert

Bei einer Anfrage – sagen wir „Flug von Berlin nach Rom für 2 Personen vom 31.10. auf den 2.11. in Euro“ – passiert
in dieser Reihenfolge:

1. **Platzhalter füllen:** Der Auftrag wird in konkrete Werte übersetzt. Fehlt ein Wert (etwa das Rückflugdatum),
   greift eine dokumentierte Regel: „3 Tage Aufenthalt = 2 Nächte“, „nächster Samstag mit mindestens 7 Tagen Vorlauf“.
   Jeder angewandte Default wird als **Annahme** festgehalten – nichts wird stillschweigend erfunden.
2. **Typen korrigieren:** Manche Werkzeuge wollen eine Zahl, wo der Platzhalter eine Zeichenkette liefert
   (z. B. „4 Sterne“ statt 4). Das wird korrigiert – auch verschachtelt, z. B. in einer Liste von Belegungen.
3. **Alle Quellen gleichzeitig fragen:** Bis zu acht Quellen laufen parallel. Im Testlauf: 9 Flugquellen,
   Gesamtsumme der Laufzeiten 46 Sekunden, Wanduhrzeit unter 17 Sekunden – der Parallelitätsgewinn ist real.
4. **Antworten übersetzen:** Jede Quelle antwortet anders. Eine liefert JSON, eine eine Markdown-Tabelle, eine
   schiebt JSON als Zeichenkette in ein Feld, eine braucht zwei Anfragen (erst suchen, dann Raten abfragen).
   Der Übersetzer bringt alles auf dieselben Felder.
5. **Platzhalter-Preise verwerfen:** Manche Anbieter liefern 0 € als Platzhalter für „Preis auf Anfrage“. Solche
   Einträge fliegen raus – sonst würde ein Nullpreis den Vergleich gewinnen.
6. **Preise vergleichbar machen:** Das ist der heikelste Schritt. Die Quellen rechnen verschieden:

   | Quelle | Wie sie rechnet | Beispiel im Test |
   |---|---|---|
   | trvl, fli, Skiplagged | **pro Person** | 183,31 € je Person → 366,62 € für zwei |
   | maqami-travel, octotrip, alice, flights-gf | **pro Reise** (alle Personen zusammen) | 373,40 € für zwei → 186,70 € je Person |
   | stay-Engines | **pro Nacht und Zimmer** | 61,00 € je Nacht |
   | maqami-Hotels | **pro Aufenthalt** (alle Nächte) | 490,19 € für den Aufenthalt |

   Ohne diese Angleichung wäre bei zwei Personen der Vergleich schlicht falsch. Jede Quelle muss deshalb
   angeben, wie sie rechnet. Und wenn eine Quelle das **nicht** eindeutig belegt (bei zwei geprüften Scrapern), wird
   das vermerkt: Das Angebot erscheint weiter in der Liste, darf aber den „günstigsten“-Platz nicht besetzen.
   Im Testlauf lag so ein unplausibel niedriger Wert (110,50 € für Berlin–Rom hin und zurück) nicht mehr vorn.
7. **Entdoppeln und sortieren:** Gleiche Tarife desselben Anbieters werden zusammengefasst (im Test: 30 rohe
   Angebote → 22 nach dem Entfernen von Dubletten).
8. **Günstigsten heraussuchen** und **jede Quelle mit Status melden** – dazu gleich mehr.

### 3.3b Was passiert, wenn eine Quelle kaprutte Zahlen liefert

Manche Anbieter antworten zwar, liefern aber Unsinn – etwa 0,01 € statt 180 €. Solche Werte werden vom System
**erkannt und verworfen**: Das Angebot fliegt raus, die Quelle wird als *kaputt* gemeldet, und ihre übrigen
Tarife werden ebenfalls nicht für den Vergleich benutzt. Das System sagt dann ausdrücklich, dass diese Quelle
korrupte Daten liefert – und nennt den **günstigsten Preis einer anderen, sauberen Quelle**. Sind alle Quellen
kaputt, gibt es **gar keine** Preisauskunft (lieber nichts als eine falsche Zahl).

Erkannt werden drei Muster: Preise unter der fachlichen Untergrenze der Reiseart (ein Flug unter 4,99 € gibt es
nicht), typische Fehlerwerte wie 0,01 € und Preise, die weit unter dem Durchschnitt derselben Quelle liegen –
das letzte Muster fängt Fehler ab, die „fast plausibel“ aussehen.

### 3.3 Was passiert, wenn eine Quelle blockiert ist

Gar nichts Dramatisches: Die betroffene Quelle wird als „fehlgeschlagen“ vermerkt, mit dem **wörtlichen**
Fehlerbild des Anbieters, und alle anderen Quellen liefern weiter. Aus dem Testlauf:

```
alice-flights   400 Client Error: Bad Request for url: https://api.alice.co.il/flights/search
skiplagged      HTTP 429 ({"type":".../error-1015/","title":"Error 1015: You are being rate…"})
```

Das ist der Grund, warum mehrere Quellen überhaupt nötig sind: Im Testlauf fielen Quellen regelmäßig einzeln aus
(Google-Flights-Server im „Cooldown“, Cloudflare-Sperre, Akamai-Sperre bei Expedia/Hotels.com) – und das Ergebnis
trotzdem gültig blieb.

### 3.4 Sonderfälle, die ohne Programmcode gelöst sind

* **Antwort als Markdown-Tabelle** (Skiplagged): Spaltenzuordnung steht in der Konfiguration.
* **Antwort im Fließtext** („EUR 289.31“): ein Muster holt die Zahl heraus.
* **Antwort mit JSON als Zeichenkette**: wird ausgepackt.
* **Zweistufige Quellen:** „erst suchen, dann Preise für die gefundenen Objekte abfragen“ – je Ergebnis einzeln oder
  gesammelt für alle gefundenen IDs; das Ergebnis wird anhand der Objekt-ID wieder zusammengeführt, damit Name
  und Koordinaten erhalten bleiben.
* **Mehrere Preise je Hotel** (Zimmertypen und Raten je Anbieter): werden zu je einem Angebot aufgefächert.

### 3.5 Was die Recherche als wichtigsten Fund brachte

Von 22 geprüften Flugquellen liefert **genau eine** ein echtes Steuerfeld: `maqami-travel` – dort steht der
Endpreis aufgeteilt in Grundpreis, Steuern, Gebühren und Summe (Testbeleg: 369,25 € = 346,22 € + 23,03 € + 0 €).
Bei Hotels sind es drei Quellen, die Steuern **positioniert** ausweisen, inklusive des Kennzeichens „enthalten“ oder
„nicht enthalten“ – bei einer Quelle fand sich sogar eine Position „RESORT 20,00 €, nicht enthalten“. Das schließt
eine Lücke, die vorher jede Hotelempfehlung hatte: Man konnte vorher nur sagen „Steuerstatus unbekannt“, jetzt kann man
sagen, ob er enthalten ist.

---

## 4. Erweiterung 2 – Intelligente Kombination

### 4.1 Die drei Varianten

Für denselben Auftrag (2 Personen, 2 Nächte) rechnet das System drei Varianten durch und nennt die billigste:

| Variante | Wie gerechnet | Ergebnis im Testlauf |
|---|---|---|
| **Rundflug + Hotel getrennt** | günstigster Rundflug (Endpreis mit Gepäck) × 2 Personen + günstigstes Hotel × 2 Nächte | **588,62 €** |
| **Gabelflug + Hotel getrennt** | günstigster Einweg (Hin) + günstigster Einweg (Rück), je × 2 Personen, + Hotel | **558,76 €** |
| **Pauschalreise** | Pauschalpreis aus einer Pauschalquelle | in diesem Lauf nicht verfügbar |

**Empfehlung des Laufs: Gabelflug, 558,76 € – 29,86 € günstiger** als Rundflug + Hotel. Die Bestandteile waren
konkret: Hinflug Ryanair, Rückflug LOT Polish, Hotel „Hotel Roma Tor Vergata“ zu 61,00 € je Nacht.

### 4.2 Die Begründung – und ihre Grenze

Jede Empfehlung wird begründet, und zwar mit zwei Dingen: dem **Live-Preisvergleich** und der **Beleglage**.

Die Belege stammen aus der Recherche nach offiziellen Preisberichten und Behördenquellen – 19 Einträge, jeweils mit
Verlag, Datum, URL und **wörtlichem Zitat**. Für die empfohlene Variante wurden E1 bis E5 und E7 herangezogen, etwa:

* **E1 (KAYAK, 02.10.2026, „stark“):** „Piecing together two one-way tickets could cut airfare by as much as
  30 % internationally and 29 % domestically.“
* **E4 (EU-Kommission, „stark“):** „If you booked an outbound and a return flight separately with different airlines
  and the outbound flight is cancelled, reimbursement is only due for the cancelled flight.“

Und – wichtig – die **Gegenpositionen** werden mitgeführt: **E6** (derselbe Anbieter misst bei eigenen Stichproben,
dass Round-Trips *meist günstiger* sind, im Beispiel New York–London 119 $ günstiger), **E16/E17** (Pauschalreise
haftet, Insolvenzabsicherung, kostenfreie Behebung; EU-Richtlinie vom April 2026 mit 537 Ja-Stimmen im Parlament),
**E14** (Pauschale erzielt sogar höhere Hotel-ADR, Stornoquote einzeln 2,6-fach höher).

Deshalb steht in jeder Ausgabe ausdrücklich die **Evidenz-Grenze**: Die Belege zeigen ein *mögliches*
Sparpotenzial getrennter Buchung, aber **keine** allgemeine Regel „getrennt ist immer günstiger“. Die Logik ist
deshalb **vergleichend statt behauptend**: Sie rechnet live, zitiert die Belege und weist die Grenze aus. Getrennt
buchen lohnt sich nur, wenn Anschlussschutz, Gepäckdurchgang oder Umbuchbarkeit nicht zählen; das Paket lohnt sich
bei Insolvenzschutz, Beistand und kostenfreiem Storno.

---

## 5. Erweiterung 3 – Preis-Alarm

### 5.1 Was der Wächter tut

Der Wächter macht dasselbe wie die Suche – er fragt alle konfigurierten Quellen –, schreibt aber das **Ergebnis
in eine Verlaufsdatei** statt es nur anzuzeigen. Aus vielen Messpunkten entstehen zwei Alarmtypen:

* **Budget-Alarm:** Der Preis (je Person oder für die ganze Reise, einstellbar) fällt auf oder unter das
  Nutzerbudget. Beispiel aus dem Test: „Preis 110,50 EUR (gesamt: 221,0) liegt unter/auf dem Budget 400.0 EUR“.
* **Tiefpunkt-Alarm:** Der Preis fällt unter eine Marke, die aus dem Beobachtungsfenster selbst stammt – z. B. auf
  95 % des Medians der letzten sieben Tage. Beispiel aus dem Test: „Tiefpunkt: 110,50 EUR ≤ Referenz 213,1
  (Median 224,32, 50,7 % unter Median)“.

Damit wird nicht auf jede kleine Bewegung reagiert, sondern nur auf ein echtes Tief bzw. auf das Budget.

### 5.2 Gegen doppelte Alarme

* **Cooldown:** Nach einem Alarm bleibt es 24 Stunden still – außer der Preis sinkt um mindestens 3 % gegenüber
  dem letzten Alarm. Im Test: Der Budget-Alarm um 18:05 und der Tiefpunkt-Alarm um 18:38 (33 Minuten später) wurden
  **beide** ausgelöst, weil der Preis um 25 % gefallen war – mit dem Vermerk „Cooldown überschrieben“.
* **Preis-Dedup:** Derselbe Preis löst nicht erneut aus.
* **Sicherheitsnetz:** Unter zwei Beobachtungen gibt es keinen Tiefpunkt-Alarm (man kann aus einem einzigen
  Messpunkt keinen Tief ableiten).
* **Datenlage-Gate:** Bevor ein Alarm aus den Verlaufdaten kommt, prüft der Wächter, ob die Datenlage überhaupt
  trägt: Braucht er mehrere verschiedene Quellen? Ist der jüngste Wert noch nicht zu alt? Waren im letzten
  Durchlauf genug Quellen erfolgreich? Ist das nicht der Fall, schweigt er – und sagt, warum („Datenlage dünn“).
  Grund: Wenn drei von neun Anbietern ausfallen, kann der Median aus einer völlig anderen Preisspanne stammen
  und trotzdem einen Alarm auslösen. Das Budget-Alarm bleibt davon unberührt – der hängt nur am aktuellen Preis.
* **Zwei Ablagen für den Verlauf:** Standard ist eine einfache Textdatei (grep-freundlich). Für sehr lange
  Verläufe gibt es zusätzlich eine Datenbank-Datei mit Schnellindex – dann findet das System die Werte der
  letzten Tage auch bei hunderttausend Messpunkten sofort. Welche Ablage schneller ist, misst das System
  selbst (`alerts/bench_history.py`).
* **Zustellung mit Empfangsbestätigung:** Bevor ein Alarm verschickt wird, landet er in einer **Warteschlange**
  (`alerts_pending.jsonl`). Erst danach wird er zugestellt. Geht der Versand daneben (Netzwerkfehler,
  Zeitüberschreitung), bleibt der Alarm in der Warteschlange und wird im nächsten Durchlauf erneut versucht
  (mit Wartezeit 5/15/60 Minuten). Derselbe Alarm wird **nicht doppelt** verschickt: Jeder Alarm bekommt einen
  Fingerabdruck aus Route, Regel, Preis und Regel-Fassung. Und: Wurde die Regel zwischen Auslösung und
  Zustellung geändert, wird der Alarm **nicht** verschickt – sonst käme ein Alarm nach, der zu einer alten
  Regel gehört.

* **Mehrere Empfänger:** Der Alarm kann an mehrere Kanäle gehen (Programm, Webhook, Slack, ntfy, gotify,
  Telegram, E-Mail). Jeder Kanal hat seinen eigenen Status: Ist einer nicht erreichbar, bekommen die anderen
  den Alarm trotzdem, und nur der ausgefallene Kanal wird später erneut versucht. Für Webhooks wird die
  Meldung zusätzlich mit einer **digitalen Unterschrift** (HMAC-SHA256 über Inhalt und Zeitstempel) versehen –
  so kann der Empfänger prüfen, dass die Meldung echt ist und nicht unterwegs verändert wurde.

### 5.3 Was gespeichert wird

| Datei | Inhalt |
|---|---|
| `alerts/state/history.jsonl` | eine Zeile je Messung: Zeit, Preis, Endpreis, Quelle, Werte aller Quellen, Zusatzsignale |
| `alerts/state/alerts.jsonl` | eine Zeile je ausgelöstem Alarm: Zeit, Regel, Preis, Quelle, Begründungstext |
| `alerts/state/last_alert.json` | Zeit, Preis und Regel des letzten Alarms (Grundlage für Cooldown und Dedup) |
| `alerts/state/alerts_pending.jsonl` | die Warteschlange: jeder Alarm mit Fingerabdruck, Zustand (`pending`/`acked`/`failed`), Versuchszahl und nächstem Versuch |

Im Testlauf: **10 Messpunkte**, Median 233,31 €, Tiefpunkt 110,50 €, drei ausgelöste Alarme.

### 5.4 Zusätzliche Signale vom Anbieter

Der Wächter liest zusätzlich die eigene Preisüberwachung des Flugwerkzeugs: laufende Wächter mit Zielpreis, deren
Preisreihe, den Provider-Status (welche Anbieter gerade „Cooldown“ haben) und die Datums-Suche. Die native
Preisreihe fließt in die eigene Statistik ein – so bleibt die Beobachtung auch dann nutzbar, wenn der eigene
Wächter einmal ausfällt.

### 5.5 Wann er läuft

* **Einmalig** (für cron): ein Durchlauf, danach beendet.
* **Dauerbetrieb** im eigenen Takt (für Container ohne cron).
* **Systemd-Timer** (jede Stunde, mit „Persistent“ – verpasste Läufe werden nachgeholt) oder **Cron**
  (Beispielzeilen liegen bei).
* **Nur prüfen** ohne etwas zu schreiben (für Tests).

---

## 5b. Die Weboberfläche

Wenn du lieber klickst als Befehle tippst: `bash ui/start.sh` und dann
<http://127.0.0.1:8077> aufrufen.

* **Suchen:** Start, Ziel, Datum, Rückkehr, Personen, Budget – und anklicken, was du suchst
  (Flüge, Hotels, Fähren, Kreuzfahrten). Die Suche fragt alle Quellen parallel ab; das dauert
  ein bis zwei Minuten. Währenddessen siehst du live, welche Quelle antwortet und welche gerade
  gesperrt ist.
* **Ergebnisse:** je Kategorie das günstigste Angebot, eine Liste der besten Treffer mit
  Detail-Link, dazu die **Bündelung** (was ist getrennt billiger, was als Paket?) mit Begründung
  und dem Hinweis, wie belastbar diese Regel ist. Quellen, die ausgefallen sind, stehen dabei.
* **Detail:** Endpreis inklusive Gepäck, Steuerstatus, Flugabschnitte, Warnhinweise (getrennte
  Tickets, Selbstverbindung …) und der **Buchungslink** zum Anbieter. Ist für den Anbieter ein
  Partnerprogramm eingerichtet, steht über dem Link **„Anzeige · Affiliate-Link“** und darunter,
  dass wir eine Provision erhalten und der Preis gleich bleibt. Fehlt eine Kennung, bleibt der
  Link ungetaggt und die Seite sagt warum.
* **Preisalarme:** Budget (je Person oder für die ganze Reise), Tiefpunkt-Regel, Preissturz,
  Cooldown. Du kannst den Wächter sofort einmal laufen lassen und siehst danach Verlauf und
  ausgelöste Alarme.

### Wie das System Geld verdient (oder eben nicht)

Buchungslinks können Affiliate-Links sein: Bucht jemand darüber, zahlt der Anbieter uns eine
Provision. Das ändert **nichts am Preis** und **nichts an der Empfehlung** – sortiert wird
ausschließlich nach Preis. Bei Billigfliegern (Ryanair, Wizz Air, easyJet) gibt es keine Provision;
deren Links bleiben deshalb ungetaggt. Welche Partner möglich sind, steht in
`affiliate/ENTSCHEIDUNG.md`; eingerichtet werden sie in `affiliate/config.yaml` (ohne eingetragene
Kennung wird nichts getaggt). Der Link wird vor der Anzeige geprüft: Steckt die Kennung drin, passt
die Domain, und ist die Seite erreichbar?

Rechtlich bleibt es dabei: Wir sind **Vermittler**, nicht Reiseveranstalter. Jede Leistung wird beim
jeweiligen Anbieter gebucht und bezahlt; wir nehmen kein Geld entgegen und leiten keine Buchungsdaten
weiter. Die Summe in der Bündelung ist ein Vergleichswert, kein Gesamtpreis-Angebot – sonst wären wir
Reiseveranstalter mit voller Haftung (§ 651b BGB).

Wichtig: Die Oberfläche **bucht nicht** – das System hat keine Zahlfunktion. Sie bringt dich zum
Anbieter; dort schließt du den Kauf selbst ab. Und: Die Oberfläche hat keine eigene Preislogik –
empfohlen wird weiterhin der günstigste Preis, und ein Budget ist ein Hinweis, keine Auswahlregel.

## 5b2. Ortsnamen und Tippfehler

Du kannst „Toulouse“, „frankfuhrt“ oder „Rom“ eingeben – das System übersetzt das automatisch in
den richtigen Code (TLS, FRA, FCO), zeigt die Übersetzung über den Ergebnissen an und schlägt beim
Tippen passende Orte vor. Gibt es den Ort nicht, sagt es das deutlich (mit Vorschlag), statt einfach
0 Treffer zu zeigen. Für Fähren und Kreuzfahrten werden Häfen aufgelöst (Barcelona → ESBCN,
Miami → MIA), für Hotels die Stadt samt Koordinaten.

## 5c. Gefunden werden (Suchmaschinen)

Damit die Seite bei Google auftaucht, gibt es jetzt feste Seiten mit eigenem Inhalt:
`/fluege`, `/hotels`, `/faehren`, `/kreuzfahrten`, `/preisvergleich` – und für jede Strecke, die
schon einmal gesucht wurde, eine eigene Seite (z. B. `/fluege/ber-fco`) mit dem letzten Preisstand.

* **Sitemap und robots.txt** sagen Google, welche Seiten es gibt und welche nicht (Suchergebnisse
  mit Lauf-Nummer und Alarme bleiben draußen).
* **Maschinenlesbare Preise** (JSON-LD) stehen auf den Streckenseiten – aus genau den Preisen,
  die auch im Text stehen.
* **Keine erfundenen Sterne:** Bewertungen zeigen wir nicht, weil wir keine echten haben.
* **Prüfen:** `python3 seo/validate.py` sagt dir nach einem Start, ob alles stimmt.

Wichtig: Eine gute Position bei Google braucht Zeit und Inhalte – die Technik ist die
Voraussetzung, nicht die Garantie.

## 6. Der Prüfrahmen – die Schleife

### 6.1 Eine Runde, Schritt für Schritt

1. **Ordner anlegen:** Jede Runde bekommt einen eigenen Ordner (`runs/round_1` …). Darin landen später die
   Rohdaten, die Ergebnisse und die Bewertung. Das hält die Spuren sauber getrennt.
2. **Auftrag ablegen:** Der Wunsch des Nutzers wird als Datei in den Ordner geschrieben – damit später
   nachvollziehbar ist, **worauf** die Runde geantwortet hat.
3. **Ausführen:** Ein separater Agent-Prozess bekommt das Aufgabenheft plus den Auftrag und arbeitet ab. Er darf nur
   die freigegebenen Werkzeuge benutzen und muss seine Rohdaten in der Runde ablegen.
4. **Ergebnis prüfen (Lauf-Check):** Ist die Antwort unbrauchbar (Rate-Limit-Meldung, abgeschnittenes Protokoll,
   fehlende Rohdateien), wird die Runde **wiederholt** – bis zu fünfmal, mit Wartezeit. Im Archiv sind 16
   solcher Fehlfälle dokumentiert: 6 abgeschnittene Läufe, 5 Rate-Limit-Läufe, 5 Bewertungen ohne Note.
5. **Bewerten:** Ein **zweiter, unabhängiger** Prozess prüft die Runde – er bekommt den Auftrag, den Rundenordner
   und das Protokoll und darf nur lesen. Er vergleicht das, was behauptet wurde, mit den Rohdaten.
6. **Noten ziehen:** Die erste Zeile der Bewertung muss exakt „SCORE: <Zahl>“ lauten; alles andere wird ignoriert.
7. **Übernehmen oder verwerfen:** Ein Prompt, der mindestens so gut bewertet wurde wie alle vorherigen, wird zum
   „besten Prompt“. Vorher wird geprüft, ob er überhaupt ein Prompt ist (siehe unten).
8. **Verbessern:** Sind Kriterien nicht erfüllt, bekommt ein dritter Prozess – der **Proposer** – nur diese
   nicht erfüllten Kriterien und darf **nur Regeln ergänzen**, niemals Ergebnisse übernehmen. Sein Vorschlag wird
   der Prompt der nächsten Runde.
9. **Abbruch:** Die Schleife endet, wenn mindestens drei Runden gültig **und** mindestens drei Runden mit Note
   mindestens 0,9 vorliegen (höchstens acht Runden).

### 6.2 Das Prüfheft (fünf Kriterien, sechs Deckel)

Die Note ist die Summe von fünf Kriterien zu je 0,2 Punkten. **Was nicht belegt ist, gilt als nicht erfüllt.**

| Kriterium | Wofür |
|---|---|
| K1 Echte Flugdaten | Jeder genannte Preis steht wörtlich in den Rohdaten |
| K2 Günstigster Flug | Es ist der billigste Tarif der Hauptsuche, die Preisbasis ist belegt, die Summe für alle Personen ist nachvollziehbar |
| K3 Flugqualität und Endpreis | Höchstens so viele Stopps wie erlaubt, Endpreis beziffert, Steuerstatus benannt, Warnhinweise übernommen |
| K4 Hotel, Distanz und Steuern | Passende Sterne und Währung, Entfernung aus den Koordinaten berechnet, Steuerstatus aus dem Detailabruf, Summe für die Nächte, Auswahlregel eingehalten |
| K5 Quellen, Einschränkungen, Buchung | Werkzeugaufrufe benannt, Einschränkungen dokumentiert, Buchungslinks vorhanden, Parameter vollständig, nichts erfunden |

Und die **Deckel** – sie verhindern, dass ein gutes Gesamtbild eine schlechte Tatsache überdeckt:

| Deckel | Wirkung |
|---|---|
| (a) keine echten Flugdaten | höchstens 0,5 |
| (b) Distanz nicht berechnet oder Koordinate ohne Herkunftsnachweis | höchstens 0,5 |
| (c) mehr Stopps als erlaubt | höchstens 0,75 |
| (d) Steuer- oder Endpreis nicht belegt | höchstens 0,75 |
| (e) kein passendes Hotel | höchstens 0,5 |
| (f) ein erfundener Wert | das betroffene Kriterium 0 |

Das entspricht genau der Anforderung „mehr als ein Stopp oder nicht belegte Steuern ⇒ unter 0,8“.

### 6.3 Die drei Schutzmechanismen, die sich bewährt haben

* **Prompt-Validierung.** In einem Vorlauf schrieb der Vorschlags-Agent statt eines Prompts die Fehlermeldung des
  Providers in die Datei („Provider rate limit reached…“, 81 Zeichen). Diese Datei wurde als Prompt der nächsten
  Runde verwendet – die Runde lief mit einem bedeutungslosen Auftrag und scored 0,0. Heute wird jede Prompt-Datei
  geprüft: nicht leer, mindestens 800 Zeichen, kein Fehltext-Muster, keine Vorwortfloskel, und sie muss die fünf
  Pflichtmarken enthalten (`params.json`, `raw_flights.json`, `raw_hotels.json`, `{adults}`, `max_stops`).
  Getestet: echter Prompt → gültig, Rate-Limit-Fehlermeldung → abgewiesen.
* **Wiederholungen statt Aufgeben.** Rate-Limits und abgeschnittene Läufe werden bis zu fünfmal wiederholt, mit
  Wartezeit; das Kostet Zeit, aber keine Runde.
* **Wiederaufnahme.** Bricht ein Lauf ab, kann die Schleife an der letzten Runde weitermachen, statt vorne
  anzufangen und alles zu verlieren. Genau damit wurde der letzte erfolgreiche Durchlauf fertiggestellt:
  „RESUME: Start bei Runde 5 (successful=2, target_hits=2, best=1.0)“.

### 6.4 Ergebnis des letzten Laufs

Vier Runden, Noten **1,0 / 0,0 / 1,0 / 1,0** – also drei Runden über der Zielmarke 0,9 (Ziel: 3 Runden mit
≥ 0,9), kein Modellfehler, kein Provider-Ausfall, Bestwert 1,0. Der Verlauf zeigt die Schleife bei der Arbeit:

* **Runde 1 (1,0):** alle fünf Kriterien erfüllt – der Aufgabenheft-Text aus der Vorversion genügt.
* **Runde 2 (0,0):** das im Protokoll genannte Hotel wich vom maschinell berechneten Endzustand ab
  (anderes Hotel, andere Distanz). Weil die Pflicht-Kriterien als **Gate** wirken (K4 = Herkunftsnachweis der
  Koordinate), ist die Note auf 0 gefallen – nicht auf einen weichen Deckelwert.
* **Runde 3 (1,0):** der Vorschlags-Agent hat aus dem einen nicht erfüllten Kriterium vier Regeln abgeleitet
  und als **Änderungsliste** geschickt (Hinzufügen von R001–R004). Die Regeln wurden in den Aufgabenheft-Text
  eingearbeitet, der Rest des Textes blieb unverändert – und die Note war wieder 1,0.
* **Runde 4 (1,0):** Bestätigung mit dem verbesserten Aufgabenheft.

Das Regel-Ledger weist die vier neuen Regeln als **hilfreich** aus (in der Runde mit Note 1,0 aktiv, ohne
Schaden). Läufe, die am Provider scheiterten, zählen nicht als Modellfehler und werden nachbewertet, statt die
ganze Runde zu wiederholen.

---

## 7. Wie alles zusammenspielt

Ein vollständiger Durchlauf (`demo.sh`) zeigt die Kette:

1. **Abdeckung:** 9 Flugquellen (8 erfolgreich, 1 mit HTTP-Fehler) und 6 Hotelquellen (alle erfolgreich) laufen
   parallel. Ergebnis: 23 gemergte Flugangebote, günstigster **183,31 € je Person** (Endpreis 233,31 € inklusive
   „+15 € Handgepäck, +35 € Aufgabegepäck“); 25 Hotelangebote, günstigstes **61,00 € je Nacht** („Hotel Roma Tor
   Vergata“, 4 Sterne). In den Einweg-Suchen fielen zwei Quellen aus (HTTP 400 und HTTP 429) – ohne die übrigen
   Quellen nicht weitergekommen wären.
2. **Bündelung:** Aus denselben Daten werden drei Varianten gerechnet. Empfehlung: Gabelflug **558,76 €** statt
   Rundflug + Hotel **588,62 €** (29,86 € günstiger), begründet mit den Belegen E1–E5, E7 und der ausgewiesenen
   Evidenz-Grenze.
3. **Alarm:** Der Wächter nimmt denselben Abruf als Messpunkt, schreibt ihn in den Verlauf und meldet den
   Budget- bzw. Tiefpunkt-Alarm – im Test 110,50 € gegen ein Budget von 400 € und 50,7 % unter dem Median.
4. **Prüfrahmen:** Sollte eine Anfrage in die Schleife gehen, arbeitet der Agent dieselben Regeln ab, und ein
   unabhängiger Prüfer entscheidet anhand der Rohdaten, ob das Ergebnis trägt.

Kurz: Die Erweiterungen liefern **Daten, Entscheidung und Beobachtung**; die Schleife sorgt dafür, dass das
Ergebnis **belegbar** ist und sich mit jedem Durchlauf verbessert.

---

## 8. Was das System kann – und was nicht

**Kann:**
* 15 aktive Preisquellen für Flüge und Hotels, alle keyless, alle parallel abfragbar, per Konfiguration erweiterbar.
* Vergleich trotz unterschiedlicher Preisbasen (pro Person / pro Reise / pro Nacht / pro Aufenthalt).
* Steuernachweis für Hotels aus drei Quellen – inklusive der Aussage, ob eine Position enthalten ist oder nicht.
* Bündelentscheidung mit Belegen **und** Gegenbelegen.
* Preisbeobachtung mit Budget- und Tiefpunkt-Alarm, Cooldown gegen Alarmflood.
* Ein Prüfrahmen, der unvollständige oder erfundene Ergebnisse nicht durchlässt.

**Kann nicht (ehrlich benannt):**
* Für **Flüge** liefert nur eine von 22 geprüften Quellen ein Steuerfeld. „Steuern inklusive“ ist bei Flügen
  eine Aussage über die Anbietersemantik, kein gemessener Feldwert – das System sagt das auch so.
* Den Begriff **„Resortgebühr“** kennt keines der Werkzeuge. Belegbar ist nur „Steuern und Gebühren sind
  enthalten“ als Summe.
* Keine **Buchung**: Es gibt kein Buchungs-Werkzeug. Das System liefert geprüfte Preise und die Links; gebucht wird
  manuell. (Die Bündelung rechnet bewusst eine **Pauschalvariante** mit, wenn eine Pauschalquelle konfiguriert ist.)
* Die kostenlosen Anbieter sind **rate-limit-anfällig** (Google-Cooldown, Cloudflare, Akamai). Die Mehrquellen-
  Abfrage ist die Gegenmaßnahme, nicht die Vermeidung.
* Der **Preis-Alarm braucht Tage**, nicht Sekunden: Ein Tiefpunkt lässt sich nicht aus einem Messpunkt ableiten
  (deshalb die Mindestzahl an Beobachtungen und das 7-Tage-Fenster).
* Ein Fahrzeug für die Reise war über die vorhandenen Quellen **nicht** buchbar: Der einzige Mietwagen-Anbieter
  ist partner-geschützt (Schlüssel nötig). Das System meldet das als „nicht verfügbar“ mit Grund und rechnet statt
 dessen Flughafen-Transfers aus.
