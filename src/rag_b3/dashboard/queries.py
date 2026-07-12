"""Consultas read-only para o dashboard de observabilidade da ingestão
(plan.md Fase 2 — "observabilidade contínua sobre ingestion_job_run")."""

from datetime import date, datetime, timezone

from psycopg import Connection


def recent_job_runs(conn: Connection, limit: int = 30) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select source, status, started_at, finished_at, summary
            from ingestion_job_run
            order by started_at desc
            limit %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    runs = []
    for source, status, started_at, finished_at, summary in rows:
        duration_seconds = (
            (finished_at - started_at).total_seconds() if finished_at else None
        )
        runs.append(
            {
                "source": source,
                "status": status,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat() if finished_at else None,
                "duration_seconds": duration_seconds,
                "summary": summary,
            }
        )
    return runs


def latest_status_by_source(conn: Connection) -> list[dict]:
    """Último status de cada job (para o indicador de saúde no topo)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select distinct on (source) source, status, started_at, finished_at
            from ingestion_job_run
            order by source, started_at desc
            """
        )
        rows = cur.fetchall()
    return [
        {
            "source": source,
            "status": status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat() if finished_at else None,
        }
        for source, status, started_at, finished_at in rows
    ]


def ibov_freshness(conn: Connection) -> dict:
    with conn.cursor() as cur:
        cur.execute("select min(trade_date), max(trade_date), count(*) from ibov_daily_history")
        min_date, max_date, count = cur.fetchone()
    days_stale = (date.today() - max_date).days if max_date else None
    return {
        "min_date": min_date.isoformat() if min_date else None,
        "max_date": max_date.isoformat() if max_date else None,
        "count": count,
        "days_stale": days_stale,
    }


def cvm_feed_counts(conn: Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select feed_key, count(*), max(first_seen_at)
            from cvm_feed_item
            group by feed_key
            order by feed_key
            """
        )
        rows = cur.fetchall()
    return [
        {
            "feed_key": feed_key,
            "count": count,
            "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
        }
        for feed_key, count, last_seen_at in rows
    ]


def quota_history(conn: Connection, days: int = 30) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select quota_date, requests_used, effective_limit
            from hg_brasil_quota_control
            order by quota_date desc
            limit %s
            """,
            (days,),
        )
        rows = cur.fetchall()
    return [
        {"quota_date": quota_date.isoformat(), "requests_used": used, "effective_limit": limit}
        for quota_date, used, limit in rows
    ]


def build_dashboard_data(conn: Connection) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "job_runs": recent_job_runs(conn),
        "latest_status": latest_status_by_source(conn),
        "ibov_freshness": ibov_freshness(conn),
        "cvm_feed_counts": cvm_feed_counts(conn),
        "quota_history": quota_history(conn),
    }
