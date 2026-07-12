import uuid
from unittest.mock import MagicMock, patch

from rag_b3.ingestion.yahoo_finance.backfill import run_ibov_backfill
from rag_b3.ingestion.yahoo_finance.client import YahooFinanceError
from tests.conftest import load_json_fixture


class _PatchedBackfill:
    def __init__(self, fetch_return=None, fetch_side_effect=None, upsert_side_effect=None):
        self.tracker_instance = MagicMock()
        self.tracker_instance.start.return_value = uuid.uuid4()
        self.audit_instance = MagicMock()
        kwargs = {}
        if fetch_side_effect is not None:
            kwargs["fetch_ibov_chart"] = MagicMock(side_effect=fetch_side_effect)
        else:
            kwargs["fetch_ibov_chart"] = MagicMock(return_value=fetch_return)
        self._patcher = patch.multiple(
            "rag_b3.ingestion.yahoo_finance.backfill",
            JobRunTracker=MagicMock(return_value=self.tracker_instance),
            AuditLogger=MagicMock(return_value=self.audit_instance),
            upsert_backfill_bar=MagicMock(
                side_effect=upsert_side_effect if upsert_side_effect is not None else (lambda *a, **k: True)
            ),
            **kwargs,
        )

    def __enter__(self):
        self._patcher.start()
        return self

    def __exit__(self, *exc_info):
        self._patcher.stop()


def test_backfill_success_counts_new_bars():
    fixture = load_json_fixture("yahoo_finance_chart_ok.json")
    with _PatchedBackfill(fetch_return=fixture) as bf:
        summary = run_ibov_backfill(conn=MagicMock(), range_="10y")

    assert summary["bars_found"] == 2  # o 3º timestamp tem close=null
    assert summary["bars_new"] == 2
    assert summary["bars_duplicate"] == 0
    finish_args = bf.tracker_instance.finish.call_args.args
    assert finish_args[2] == "success"


def test_backfill_re_run_counts_as_duplicate():
    fixture = load_json_fixture("yahoo_finance_chart_ok.json")
    with _PatchedBackfill(fetch_return=fixture, upsert_side_effect=lambda *a, **k: False):
        summary = run_ibov_backfill(conn=MagicMock(), range_="10y")

    assert summary["bars_new"] == 0
    assert summary["bars_duplicate"] == 2


def test_backfill_fetch_failure_marks_job_failed():
    with _PatchedBackfill(fetch_side_effect=YahooFinanceError("boom")) as bf:
        summary = run_ibov_backfill(conn=MagicMock(), range_="10y")

    assert summary["bars_found"] == 0
    finish_args = bf.tracker_instance.finish.call_args.args
    assert finish_args[2] == "failed"
