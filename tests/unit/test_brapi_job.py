import uuid
from unittest.mock import MagicMock, patch

from rag_b3.config.settings import Settings
from rag_b3.config.watchlist import WatchlistTicker
from rag_b3.ingestion.brapi.errors import BrapiAuthError
from rag_b3.ingestion.brapi.job import run_brapi_ingestion


def _settings() -> Settings:
    return Settings(
        HG_BRASIL_API_KEY="dummy",
        DATABASE_URL="postgresql://unused/unused",
        BRAPI_TOKEN="dummy-token",
    )


def _watchlist(*symbols: str) -> list[WatchlistTicker]:
    return [WatchlistTicker(symbol=s) for s in symbols]


class _PatchedJob:
    def __init__(self, watchlist):
        self.tracker_instance = MagicMock()
        self.tracker_instance.start.return_value = uuid.uuid4()
        self.audit_instance = MagicMock()
        self._patcher = patch.multiple(
            "rag_b3.ingestion.brapi.job",
            load_watchlist=MagicMock(return_value=watchlist),
            JobRunTracker=MagicMock(return_value=self.tracker_instance),
            AuditLogger=MagicMock(return_value=self.audit_instance),
            upsert_stock_quote=MagicMock(),
        )

    def __enter__(self):
        self._patcher.start()
        return self

    def __exit__(self, *exc_info):
        self._patcher.stop()


def test_empty_watchlist_finishes_as_success_without_calling_client():
    with _PatchedJob(_watchlist()) as job, patch(
        "rag_b3.ingestion.brapi.job.BrapiClient"
    ) as client_cls:
        summary = run_brapi_ingestion(_settings(), conn=MagicMock())

    client_cls.assert_not_called()
    assert summary == {"requested": 0, "succeeded": 0, "failed": 0, "not_found": []}
    finish_args = job.tracker_instance.finish.call_args.args
    assert finish_args[2] == "success"


def test_full_success_in_a_single_batched_request():
    watchlist = _watchlist("PETR4", "VALE3")
    fake_client = MagicMock()
    fake_client.get_quotes.return_value = {
        "results": [
            {"symbol": "PETR4", "regularMarketPrice": 38.42},
            {"symbol": "VALE3", "regularMarketPrice": 61.10},
        ]
    }

    with _PatchedJob(watchlist) as job, patch(
        "rag_b3.ingestion.brapi.job.BrapiClient", return_value=fake_client
    ):
        summary = run_brapi_ingestion(_settings(), conn=MagicMock())

    fake_client.get_quotes.assert_called_once_with(["PETR4", "VALE3"])
    assert summary == {"requested": 2, "succeeded": 2, "failed": 0, "not_found": []}
    finish_args = job.tracker_instance.finish.call_args.args
    assert finish_args[2] == "success"


def test_ticker_missing_from_results_is_marked_not_found_without_failing_the_rest():
    watchlist = _watchlist("PETR4", "ZZZZ9")
    fake_client = MagicMock()
    fake_client.get_quotes.return_value = {
        "results": [{"symbol": "PETR4", "regularMarketPrice": 38.42}]
    }

    with _PatchedJob(watchlist) as job, patch(
        "rag_b3.ingestion.brapi.job.BrapiClient", return_value=fake_client
    ):
        summary = run_brapi_ingestion(_settings(), conn=MagicMock())

    assert summary["succeeded"] == 1
    assert summary["not_found"] == ["ZZZZ9"]
    finish_args = job.tracker_instance.finish.call_args.args
    assert finish_args[2] == "partial_success"


def test_auth_error_aborts_the_whole_job():
    watchlist = _watchlist("PETR4", "VALE3")
    fake_client = MagicMock()
    fake_client.get_quotes.side_effect = BrapiAuthError("401", "token inválido")

    with _PatchedJob(watchlist) as job, patch(
        "rag_b3.ingestion.brapi.job.BrapiClient", return_value=fake_client
    ):
        summary = run_brapi_ingestion(_settings(), conn=MagicMock())

    assert summary["succeeded"] == 0
    finish_args = job.tracker_instance.finish.call_args.args
    assert finish_args[2] == "failed"
