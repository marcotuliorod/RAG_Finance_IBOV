#!/bin/bash
# Instala e ativa os três jobs recorrentes (HG Brasil diário, poller CVM,
# brapi diário) como LaunchAgents do usuário. Idempotente: pode rodar de
# novo após editar os .plist para recarregar.
set -euo pipefail

PROJECT_DIR="/Users/marcotuliorod/Projetos/RAG_Finance_IBOV"
PLIST_DIR="$PROJECT_DIR/ops/launchd"
TARGET_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$TARGET_DIR"
chmod +x "$PLIST_DIR/run_hg_brasil.sh" "$PLIST_DIR/run_cvm_poller.sh" "$PLIST_DIR/run_brapi.sh"
mkdir -p "$PROJECT_DIR/logs"

for name in com.ragb3.hgbrasil.daily com.ragb3.cvm.poller com.ragb3.brapi.daily; do
    cp "$PLIST_DIR/$name.plist" "$TARGET_DIR/$name.plist"
    launchctl unload "$TARGET_DIR/$name.plist" 2>/dev/null || true
    launchctl load "$TARGET_DIR/$name.plist"
    echo "Instalado e carregado: $name"
done

echo ""
echo "Verificar status: launchctl list | grep ragb3"
echo "Ver logs: tail -f $PROJECT_DIR/logs/*.log"
echo "Desinstalar: $PROJECT_DIR/scripts/uninstall_launchd_jobs.sh"
