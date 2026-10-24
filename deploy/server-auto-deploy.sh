#!/bin/bash
# Auto-Deploy: GitHub main -> /home/batnini/mimo-agents -> systemd restart.
# Wird vom systemd-Timer travel-deploy.timer aufgerufen.
set -euo pipefail
REPO="$HOME/travel-git"
APP="$HOME/mimo-agents"
LOG="$HOME/deploy-travel.log"

exec 9>"$HOME/.deploy-travel.lock"
flock -n 9 || { echo "Deploy läuft bereits"; exit 0; }

exec >>"$LOG" 2>&1
echo "=== $(date -Is) ==="
cd "$REPO"

OLD=$(git rev-parse HEAD)
git fetch --prune origin main
NEW=$(git rev-parse origin/main)
if [ "$OLD" = "$NEW" ]; then
  echo "keine Änderung: $OLD"
  exit 0
fi

echo "deploy: $OLD -> $NEW"
git reset --hard origin/main

rsync -rlptz --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.venv/' \
  --exclude '.venv-*/' \
  --exclude 'attest/keys/' \
  --exclude 'attest/state/' \
  --exclude 'attest/artifacts/' \
  --exclude 'ui/state/' \
  --exclude 'alerts/state/' \
  --exclude 'providers/state/' \
  --exclude 'affiliate/state/' \
  --exclude 'resolver/state/' \
  --exclude 'logs/' \
  "$REPO/ui" "$REPO/providers" "$REPO/seo" "$REPO/resolver" \
  "$REPO/affiliate" "$REPO/alerts" "$REPO/bundling" "$REPO/attest" \
  "$REPO/docs" "$REPO/i18n" "$REPO/llms.txt" "$REPO/requirements-runtime.txt" \
  "$REPO/scripts" "$REPO/deploy" \
  "$APP/"

rsync -rlptz --delete "$REPO/rome-2star/worker_c/" "$APP/rome-2star/worker_c/"

"$APP/.venv/bin/pip" install -q -r "$APP/requirements-runtime.txt"
sudo systemctl restart reise-agent

# uvicorn braucht je nach CDP-Erreichbarkeit 5-60 s. Bis zu 80 s warten.
for _ in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8077/health; then
    echo
    echo "OK $(date -Is)"
    exit 0
  fi
  sleep 2
done

echo "FEHLER: /health nach 80 s nicht erreichbar" >&2
exit 1
