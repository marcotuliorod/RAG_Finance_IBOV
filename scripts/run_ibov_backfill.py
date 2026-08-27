#!/usr/bin/env python3
"""Backfill retroativo de série histórica diária do Ibovespa via Yahoo
Finance chart API (endpoint não-oficial, uso pessoal/pesquisa — ver
docstring de yahoo_finance.client). Rodar uma vez (ou esporadicamente,
já que é idempotente) — não é um job diário agendado como os outros dois."""

import argparse
import json
import logging
import sys
from datetime import date

from rag_b3.common.db import get_connection
from rag_b3.common.logging_config import configure_logging
from rag_b3.config.settings import get_settings
from rag_b3.ingestion.yahoo_finance.backfill import run_ibov_backfill
from rag_b3.ingestion.yahoo_finance.client import SERIES_START

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start",
        default=SERIES_START.isoformat(),
        help=f"Data de início do backfill, formato ISO (YYYY-MM-DD). Default: {SERIES_START.isoformat()} "
        "— âncora fixa, não relativa a hoje (evita que o início da série mude a cada re-execução).",
    )
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    with get_connection(settings.database_url) as conn:
        summary = run_ibov_backfill(conn, start=date.fromisoformat(args.start))
    logger.info("Resumo do backfill IBOV: %s", json.dumps(summary, ensure_ascii=False))
    return 0 if summary.get("bars_found", 0) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
