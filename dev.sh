#!/bin/zsh
# Lance le backend (FastAPI :8000) et le frontend (Vite :5180) ensemble.
# Ctrl+C arrête les deux.
cd "$(dirname "$0")"

for port in 8000 5180; do
  if lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Le port $port est déjà utilisé : l'Atelier tourne sans doute déjà dans un autre terminal."
    echo "Arrête-le (Ctrl+C dans ce terminal) ou ouvre http://localhost:5180"
    exit 1
  fi
done

# Stop both servers once, on Ctrl+C or when either exits (the trap is removed
# first so that signalling our own process group does not re-enter it).
cleanup() { trap - INT TERM EXIT; kill 0 2>/dev/null; exit 0 }
trap cleanup INT TERM EXIT

(cd backend && uv run uvicorn design_backend.api:app --host 127.0.0.1 --port 8000 --reload --reload-dir src) &
(cd frontend && npm run dev -- --open) &
wait
