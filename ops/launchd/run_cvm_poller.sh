#!/bin/bash
# Wrapper chamado pelo launchd (com.ragb3.cvm.poller) a cada 30 minutos,
# todos os dias/horas — a janela real (*/30 8-19 * * 1-5, America/Sao_Paulo)
# é aplicada aqui, não no plist, para não precisar de ~120 entradas de
# StartCalendarInterval. Fora da janela, sai sem chamar a rede.
set -euo pipefail

PROJECT_DIR="/Users/marcotuliorodgmail.com/Prj_RAG_Finance"
cd "$PROJECT_DIR"

WEEKDAY=$(TZ=America/Sao_Paulo date +%u)   # 1=segunda ... 7=domingo
HOUR=$(TZ=America/Sao_Paulo date +%H)      # 00-23

if (( WEEKDAY > 5 )); then
    echo "$(date '+%Y-%m-%d %H:%M:%S') fora do dia útil (weekday=$WEEKDAY), pulando." >> logs/cvm_poller.log
    exit 0
fi
if (( 10#$HOUR < 8 || 10#$HOUR > 19 )); then
    echo "$(date '+%Y-%m-%d %H:%M:%S') fora da janela horária (hour=$HOUR), pulando." >> logs/cvm_poller.log
    exit 0
fi

exec /opt/homebrew/bin/uv run python scripts/run_cvm_poller.py
