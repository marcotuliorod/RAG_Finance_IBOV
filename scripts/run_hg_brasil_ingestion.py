#!/usr/bin/env python3
"""Entrypoint CLI do job diário HG Brasil (RF-02). Agnóstico de scheduler —
pode ser chamado por cron, GitHub Actions, Supabase pg_cron+Edge Function,
etc. Cadência recomendada: 30 18 * * 1-5 (America/Sao_Paulo)."""

import json
import logging
import sys

from rag_b3.common.db import get_connection
from rag_b3.common.logging_config import configure_logging
from rag_b3.config.settings import get_settings
from rag_b3.ingestion.hg_brasil.job import run_hg_brasil_ingestion

logger = logging.getLogger(__name__)


def main() -> int:
    configure_logging()
    settings = get_settings()
    with get_connection(settings.supabase_db_url) as conn:
        summary = run_hg_brasil_ingestion(settings, conn)
    logger.info("Resumo do job HG Brasil: %s", json.dumps(summary, ensure_ascii=False))
    if summary["skipped_quota"] or summary["failed"] > 0:
        return 2  # partial success — sinaliza para alertas externos
    return 0


if __name__ == "__main__":
    sys.exit(main())
