#!/bin/bash
# Wrapper chamado pelo launchd (com.ragb3.brapi.daily). Cadência: 18:35
# America/Sao_Paulo, dias úteis (ver com.ragb3.brapi.daily.plist) — logo
# após o job HG Brasil (18:30), já que ambos dependem do fechamento do
# pregão.
set -euo pipefail

PROJECT_DIR="/Users/marcotuliorod/Projetos/RAG_Finance_IBOV"
cd "$PROJECT_DIR"

exec /opt/homebrew/bin/uv run python scripts/run_brapi_ingestion.py
