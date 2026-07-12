from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from rag_b3.dashboard.queries import (
    cvm_feed_counts,
    ibov_freshness,
    latest_status_by_source,
    quota_history,
    recent_job_runs,
)


def _conn_with_rows(rows):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = rows
    return conn


def _conn_with_row(row):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = row
    return conn


def test_recent_job_runs_computes_duration_and_serializes_dates():
    started = datetime(2026, 7, 12, 1, 35, 17, tzinfo=timezone.utc)
    finished = datetime(2026, 7, 12, 1, 35, 18, 500000, tzinfo=timezone.utc)
    conn = _conn_with_rows(
        [("hg_brasil", "success", started, finished, {"requested": 1})]
    )

    runs = recent_job_runs(conn, limit=10)

    assert runs[0]["source"] == "hg_brasil"
    assert runs[0]["duration_seconds"] == 1.5
    assert runs[0]["started_at"] == started.isoformat()
    assert runs[0]["summary"] == {"requested": 1}


def test_recent_job_runs_handles_unfinished_run():
    started = datetime(2026, 7, 12, 1, 35, 17, tzinfo=timezone.utc)
    conn = _conn_with_rows([("cvm_rss", "running", started, None, {})])

    runs = recent_job_runs(conn)

    assert runs[0]["finished_at"] is None
    assert runs[0]["duration_seconds"] is None


def test_latest_status_by_source_serializes_rows():
    started = datetime(2026, 7, 12, tzinfo=timezone.utc)
    conn = _conn_with_rows([("hg_brasil", "success", started, started)])

    result = latest_status_by_source(conn)

    assert result == [
        {
            "source": "hg_brasil",
            "status": "success",
            "started_at": started.isoformat(),
            "finished_at": started.isoformat(),
        }
    ]


def test_ibov_freshness_computes_days_stale():
    conn = _conn_with_row((date(2016, 7, 11), date.today(), 2485))

    result = ibov_freshness(conn)

    assert result["min_date"] == "2016-07-11"
    assert result["count"] == 2485
    assert result["days_stale"] == 0


def test_ibov_freshness_handles_empty_table():
    conn = _conn_with_row((None, None, 0))

    result = ibov_freshness(conn)

    assert result["min_date"] is None
    assert result["days_stale"] is None


def test_cvm_feed_counts_serializes_rows():
    seen = datetime(2026, 7, 12, tzinfo=timezone.utc)
    conn = _conn_with_rows([("legislacao", 10, seen)])

    result = cvm_feed_counts(conn)

    assert result == [{"feed_key": "legislacao", "count": 10, "last_seen_at": seen.isoformat()}]


def test_quota_history_serializes_rows():
    conn = _conn_with_rows([(date(2026, 7, 11), 1, 360)])

    result = quota_history(conn)

    assert result == [{"quota_date": "2026-07-11", "requests_used": 1, "effective_limit": 360}]
