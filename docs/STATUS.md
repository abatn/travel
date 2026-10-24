# Projektstatus

Stand: 24.10.2026. Diese Datei ist die einzige Übersicht über „erledigt / offen“.
Zahlen und Belege werden nur eingetragen, wenn sie geprüft sind.

## Vom Betreiber erledigt und bestätigt

| Punkt | Status | Beleg |
|---|---|---|
| Cloudflare E-Mail-Obfuskation | **aus** | Geprüft 24.10.2026: `/impressum` enthält `batniniabdelkader@yahoo.com` im Klartext, kein `email-protection` im Quelltext. |
| GitHub-Token rotiert | **teilweise** | `gh` verwendet einen neuen Token (nicht mehr der alte). **Der alte Token ist auf GitHub aber noch gültig** (HTTP 200 am 24.10.2026) und muss in den GitHub-Einstellungen gelöscht werden. |
| Steuerberater: tunesische Pflichten | **schriftlich bestätigt** | Angabe des Betreibers. Die Bestätigung liegt beim Betreiber, nicht im Repo. |

## Technisch fertig und live

| Bereich | Stand |
|---|---|
| M2 Attestierung (`POST /api/attest`) | live, 0,01 USDC auf Base, Ed25519-signiert |
| x402-Flow (GET/HEAD/POST → 402) | live, offizieller CDP-Check 25/25 |
| Discovery (`.well-known/agent-payments.json`, `llms.txt`) | live |
| M3 Capability-Katalog (`/capabilities`, `.well-known/capabilities.json`) | live |
| Umsatzbericht (`deploy/revenue_report.py`) | fertig, 15 Tests |
| Zahlungs-Watch (E-Mail bei fremden Zahlungen) | aktiv, stündlich, Testmail zugestellt |
| Monatliche Selbstzahlung (30-Tage-Regel) | aktiv, im Repo dokumentiert |
| Quellenrechte-Sperre (`providers/rights.py`) | aktiv, 4 Quellen gesperrt |

## Offen

1. **Alten GitHub-Token löschen** (er funktioniert noch).
2. **Vier Verzeichnis-Einträge** warten auf Freischaltung: gold-402 (#410), xpaysh (#1993), x402.eco (#24), x402-index (#78).
3. **Nutzungsbedingungen von 16 Quellen** prüfen, dann Status in `providers/registry.yaml` auf `approved`/`prohibited` setzen.
4. **Erster fremder Zahler** fehlt. Umsatz: 0,000000 USDC (alle bisherigen Zahlungen sind eigene).
5. **Kostenloses Beispiel** (`GET /api/attest/sample`) ist noch nicht gebaut.
6. **M5 (Prognosen)** ist vorbereitet, aber nicht begonnen; braucht eigene Historie und Mindestfallzahl.

## Entscheidungsregel

Wenn nach 60 Tagen kein fremder Zahler auftaucht, wird M2 in dieser Form eingestellt
und auf M5 gewechselt. Eigene Zahlungen zählen dabei nie als Umsatz.
