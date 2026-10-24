#!/bin/bash
# Monatliche Selbstzahlung (0,01 USDC) an den eigenen x402-Endpunkt.
# Hält das Listing in CDP-Bazaar & Verzeichnissen über der 30-Tage-Aktivitätsschwelle.
# Installation: siehe docs/DEPLOY_CONTABO.md (Abschnitt "Monatliche Selbstzahlung").
set -euo pipefail
cd /home/batnini/mimo-agents
mkdir -p attest/artifacts
/home/batnini/mimo-agents/.venv/bin/python -m attest.client \
  --base https://travel.hanibal-ai.com \
  --key-file /home/batnini/mimo-agents/attest/keys/buyer.key \
  --network eip155:8453 \
  --output /home/batnini/mimo-agents/attest/artifacts/attestation_monthly_$(date +%Y%m).json
