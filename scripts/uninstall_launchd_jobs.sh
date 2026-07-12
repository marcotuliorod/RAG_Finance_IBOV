#!/bin/bash
# Descarrega e remove os dois LaunchAgents instalados por install_launchd_jobs.sh.
set -euo pipefail

TARGET_DIR="$HOME/Library/LaunchAgents"

for name in com.ragb3.hgbrasil.daily com.ragb3.cvm.poller; do
    launchctl unload "$TARGET_DIR/$name.plist" 2>/dev/null || true
    rm -f "$TARGET_DIR/$name.plist"
    echo "Removido: $name"
done
