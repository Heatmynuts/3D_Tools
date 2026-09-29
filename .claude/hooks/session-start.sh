#!/bin/bash
# Installe les dépendances CAD (build123d) pour les sessions cloud.
# En local, l'installation est manuelle (voir docs/local-h2d.md).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if ! python3 -c "import build123d" 2>/dev/null; then
  pip install --quiet build123d
fi

# Pré-télécharge le serveur MCP build123d (même version que .mcp.json).
uv tool run --python 3.12 build123d-mcp@0.3.90 --version >/dev/null 2>&1 || true
