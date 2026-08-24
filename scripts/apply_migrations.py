#!/usr/bin/env python3
"""Aplica db/migrations/*.sql em ordem contra DATABASE_URL — substitui o
editor SQL do painel Supabase (não existe mais fora do Supabase). Fluxo
simples e sem tabela de tracking de migrações aplicadas: pensado para
"banco novo, aplica tudo uma vez" (ver docs/PRD.md — migração para Postgres
local via Docker), não para aplicar incrementalmente sobre um banco já em
produção."""

import logging
import sys
from pathlib import Path

from rag_b3.common.db import get_connection
from rag_b3.common.logging_config import configure_logging
from rag_b3.config.settings import get_settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"


def main() -> int:
    configure_logging()
    settings = get_settings()

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        logger.error("Nenhum arquivo .sql encontrado em %s", MIGRATIONS_DIR)
        return 1

    with get_connection(settings.database_url) as conn:
        for path in migration_files:
            logger.info("Aplicando %s", path.name)
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)

    logger.info("%d migrações aplicadas com sucesso", len(migration_files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
