#!/usr/bin/env python3
"""Gera o dashboard de observabilidade da ingestão (plan.md Fase 2) como um
HTML autocontido em dashboard/index.html — rodar sob demanda para atualizar
o retrato dos dados."""

import sys
from pathlib import Path

from rag_b3.common.db import get_connection
from rag_b3.config.settings import get_settings
from rag_b3.dashboard.queries import build_dashboard_data
from rag_b3.dashboard.render import render_dashboard_html

OUTPUT_PATH = Path(__file__).parent.parent / "dashboard" / "index.html"


def main() -> int:
    settings = get_settings()
    with get_connection(settings.supabase_db_url) as conn:
        data = build_dashboard_data(conn)

    html = render_dashboard_html(data)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard gerado em {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
