#!/usr/bin/env bash
# Startet die Weboberflaeche des Reise-Agent-Systems.
#   bash ui/start.sh [PORT]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8077}"
cd "$ROOT"
echo "Reise-Agent-UI: http://127.0.0.1:${PORT}"
exec python3 -m uvicorn ui.app:app --host 127.0.0.1 --port "$PORT" --log-level info
