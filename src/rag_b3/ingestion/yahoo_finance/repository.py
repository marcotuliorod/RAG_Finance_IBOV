import json
import uuid

from psycopg import Connection

from rag_b3.ingestion.yahoo_finance.models import IbovDailyBar


def upsert_backfill_bar(
    conn: Connection,
    bar: IbovDailyBar,
    job_run_id: uuid.UUID,
    raw_payload: dict,
) -> bool:
    """Insere uma barra histórica com source='yahoo_finance_backfill'.
    ON CONFLICT DO NOTHING de propósito: se já existe uma linha para essa
    data (ex.: o job diário do HG Brasil já rodou hoje), o backfill nunca
    sobrescreve — a ingestão contínua é sempre a fonte mais autoritativa
    para o dia corrente. Retorna True se inseriu (novo), False se já existia."""
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into ibov_daily_history
                (trade_date, open, high, low, close, volume, variation_percent,
                 source, raw_payload, job_run_id)
            values (%s, %s, %s, %s, %s, %s, %s, 'yahoo_finance_backfill', %s, %s)
            on conflict (trade_date) do nothing
            returning trade_date
            """,
            (
                bar.trade_date,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                bar.variation_percent,
                json.dumps(raw_payload, default=str),
                job_run_id,
            ),
        )
        return cur.fetchone() is not None


def upsert_daily_close_from_hg_brasil(
    conn: Connection,
    trade_date,
    close: float | None,
    variation_percent: float | None,
    job_run_id: uuid.UUID,
    raw_payload: dict,
) -> None:
    """Chamado pelo job diário do HG Brasil (RF-02) para manter
    ibov_daily_history como fonte única de série histórica, mesmo no dia a
    dia — não só no backfill. DO UPDATE aqui de propósito: a ingestão
    contínua é a mais autoritativa para o dia corrente."""
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into ibov_daily_history
                (trade_date, close, variation_percent, source, raw_payload, job_run_id)
            values (%s, %s, %s, 'hg_brasil', %s, %s)
            on conflict (trade_date) do update set
                close = excluded.close,
                variation_percent = excluded.variation_percent,
                source = excluded.source,
                raw_payload = excluded.raw_payload,
                job_run_id = excluded.job_run_id,
                ingested_at = now()
            """,
            (trade_date, close, variation_percent, json.dumps(raw_payload, default=str), job_run_id),
        )
