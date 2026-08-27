#!/usr/bin/env python3
"""Entrypoint CLI do job diário brapi.dev (cotação por ticker da watchlist).
Agnóstico de scheduler — pode ser chamado por cron, launchd, etc. Cadência
recomendada: mesma janela do HG Brasil ou logo após (18:35 dias úteis,
America/Sao_Paulo), já que ambos dependem do fechamento do pregão."""

import json
import logging
import sys

from rag_b3.common.db import get_connection
from rag_b3.common.logging_config import configure_logging
from rag_b3.config.settings import get_settings
from rag_b3.ingestion.brapi.job import run_brapi_ingestion

logger = logging.getLogger(__name__)


def main() -> int:
    configure_logging()
    settings = get_settings()
    with get_connection(settings.database_url) as conn:
        summary = run_brapi_ingestion(settings, conn)
    logger.info("Resumo do job brapi: %s", json.dumps(summary, ensure_ascii=False))
    if summary["not_found"] or summary["failed"] > 0:
        return 2  # partial success — sinaliza para alertas externos
    return 0


if __name__ == "__main__":
    sys.exit(main())
