#!/usr/bin/env python3
"""Entrypoint CLI do poller de feeds RSS institucionais da CVM (RF-01,
escopo ajustado: regulatório/compliance). Cadência recomendada:
*/30 8-19 * * 1-5 (America/Sao_Paulo)."""

import json
import logging
import sys

from rag_b3.common.db import get_connection
from rag_b3.common.logging_config import configure_logging
from rag_b3.config.settings import get_settings
from rag_b3.ingestion.cvm_rss.job import run_cvm_rss_ingestion

logger = logging.getLogger(__name__)


def main() -> int:
    configure_logging()
    settings = get_settings()
    with get_connection(settings.supabase_db_url) as conn:
        summary = run_cvm_rss_ingestion(conn)
    logger.info("Resumo do poll CVM RSS: %s", json.dumps(summary, ensure_ascii=False))
    return 0 if summary["feeds_failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
