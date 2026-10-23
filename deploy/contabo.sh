#!/bin/bash
# Deployment auf den Contabo-Server (Caddy -> 127.0.0.1:8077).
# Aufruf: ./deploy/contabo.sh [ssh-host]   (Default: contabo)
set -euo pipefail
HOST="${1:-contabo}"
DEST="/home/batnini/mimo-agents"

rsync -a --delete \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude '.venv-x402' \
  --exclude 'attest/artifacts' \
  --exclude 'ui/state' \
  --exclude 'attest/state' \
  --exclude 'alerts/state' \
  --exclude 'attest/state/invoices.jsonl' \
  --exclude 'attest/state/*.lock' \
  --exclude 'attest/keys/buyer.key' \
  ui providers seo resolver affiliate alerts bundling attest docs llms.txt rome-2star requirements-runtime.txt \
  "$HOST:$DEST/"

ssh "$HOST" 'chown -R batnini:batnini /home/batnini/mimo-agents; systemctl restart reise-agent; sleep 3; systemctl is-active reise-agent; curl -fsS http://127.0.0.1:8077/health; echo'
