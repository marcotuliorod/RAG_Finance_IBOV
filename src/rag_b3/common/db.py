from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection


@contextmanager
def get_connection(db_url: str) -> Iterator[Connection]:
    """Conexão psycopg direta ao Postgres (Supabase), autocommit desligado.

    Usamos psycopg (não supabase-py/PostgREST) porque o budget manager
    precisa de UPDATE...RETURNING atômico via função SQL — ver
    reserve_hg_brasil_quota em db/migrations/0003_hg_brasil_quota_control.sql.
    """
    conn = psycopg.connect(db_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
