#!/bin/bash
# Wrapper chamado pelo launchd (com.ragb3.hgbrasil.daily). Cadência: 18:30
# America/Sao_Paulo, dias úteis (ver com.ragb3.hgbrasil.daily.plist).
set -euo pipefail

PROJECT_DIR="/Users/marcotuliorodgmail.com/Prj_RAG_Finance"
cd "$PROJECT_DIR"

exec /opt/homebrew/bin/uv run python scripts/run_hg_brasil_ingestion.py
