# Projektstatus

Stand: 25.10.2026. Diese Datei ist die einzige Übersicht über „erledigt / offen“.
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
| Dark/Light-Mode (gesamte UI) | fertig, 63/63 Theme-Tests; Dokumentation `ui/THEME_ENTSCHEIDUNG.md` |

## Offen

1. **Alten GitHub-Token löschen** (er funktioniert noch).
2. **Vier Verzeichnis-Einträge** warten auf Freischaltung: gold-402 (#410), xpaysh (#1993), x402.eco (#24), x402-index (#78).
3. **Nutzungsbedingungen von 16 Quellen** prüfen, dann Status in `providers/registry.yaml` auf `approved`/`prohibited` setzen.
4. ~~Erster fremder Zahler~~ **eingetroffen und geprüft**:
   - 2026-10-24 22:19 UTC: `0xA1d1C0cf717402ff3651aA4873CcF96410B01978` → 0,01 USDC,
     Tx `0x368b0ad320a4a2ef82e5cf962bbc5fac0f4990390c6a2cba6dfaefd855818397`,
     Rechnung RE-2026-000004.
   - 2026-10-25 09:43 UTC: `0x7722DfAE6bbed2Fd02Dc07455c2f5BF14bE25E4a` → 0,01 USDC,
     Tx `0xddf1028aa6766cf768189b889a21b5c6798118ef7438fb4b28bcc08af2cf0310`,
     Rechnung RE-2026-000005.
   - **Fremder Umsatz: 0,020000 USDC** aus 2 Wallets; 4 eigene Testzahlungen (0,04 USDC)
     bleiben ausgeschlossen. Bazaar-`lastUpdated` wurde durch die Zahlung aktualisiert.
5. **Kostenloses Beispiel** (`GET /api/attest/sample`) ist noch nicht gebaut.
6. **M5 (Prognosen)** ist vorbereitet, aber nicht begonnen; braucht eigene Historie und Mindestfallzahl.

## Entscheidungsregel

Wenn nach 60 Tagen kein fremder Zahler auftaucht, wird M2 in dieser Form eingestellt
und auf M5 gewechselt. Eigene Zahlungen zählen dabei nie als Umsatz.
