import uuid
from unittest.mock import MagicMock, patch

from rag_b3.config.settings import Settings
from rag_b3.config.watchlist import WatchlistTicker
from rag_b3.ingestion.hg_brasil.budget_manager import QuotaExceededError
from rag_b3.ingestion.hg_brasil.errors import HgBrasilPlanRestrictedError, HgBrasilTickerError
from rag_b3.ingestion.hg_brasil.job import run_hg_brasil_ingestion
from tests.conftest import InMemoryBudgetRepository


def _settings(on_insufficient_budget: str = "partial") -> Settings:
    return Settings(
        HG_BRASIL_API_KEY="dummy",
        SUPABASE_DB_URL="postgresql://unused/unused",
        HG_BRASIL_ON_INSUFFICIENT_BUDGET=on_insufficient_budget,
    )


def _watchlist(*symbols: str) -> list[WatchlistTicker]:
    return [WatchlistTicker(symbol=s) for s in symbols]


class _PatchedJob:
    """Contexto com todas as dependências que tocam Postgres/HTTP mockadas —
    isola o teste no fluxo de controle de job.py (preflight, loop de
    tickers, esgotamento de cota, status final). Guarda referências diretas
    aos mocks para asserção (patch.multiple só devolve um dict quando se usa
    o sentinel DEFAULT, então mantemos as instâncias nós mesmos)."""

    def __init__(self, watchlist, effective_limit=360):
        self.tracker_instance = MagicMock()
        self.tracker_instance.start.return_value = uuid.uuid4()
        self.audit_instance = MagicMock()
        self.upsert_daily_close_mock = MagicMock()
        self._patcher = patch.multiple(
            "rag_b3.ingestion.hg_brasil.job",
            load_watchlist=MagicMock(return_value=watchlist),
            JobRunTracker=MagicMock(return_value=self.tracker_instance),
            AuditLogger=MagicMock(return_value=self.audit_instance),
            upsert_market_snapshot=MagicMock(),
            upsert_stock_quote=MagicMock(),
            upsert_daily_close_from_hg_brasil=self.upsert_daily_close_mock,
            PostgresBudgetRepository=MagicMock(
                return_value=InMemoryBudgetRepository(effective_limit=effective_limit)
            ),
        )

    def __enter__(self):
        self._patcher.start()
        return self

    def __exit__(self, *exc_info):
        self._patcher.stop()


def test_market_snapshot_feeds_ibov_daily_history():
    watchlist = _watchlist()  # sem tickers — watchlist desativada (ver config/watchlist.yaml)
    fake_client = MagicMock()
    fake_client.get_market_snapshot.return_value = {
        "results": {"stocks": {"IBOVESPA": {"points": 177866.38, "variation": 2.97}}}
    }

    with _PatchedJob(watchlist, effective_limit=360) as job, patch(
        "rag_b3.ingestion.hg_brasil.job.HgBrasilClient", return_value=fake_client
    ):
        run_hg_brasil_ingestion(_settings(), conn=MagicMock())

    job.upsert_daily_close_mock.assert_called_once()
    call_args = job.upsert_daily_close_mock.call_args.args
    assert call_args[2] == 177866.38  # close
    assert call_args[3] == 2.97  # variation


def test_market_snapshot_without_ibovespa_data_skips_daily_history():
    watchlist = _watchlist()
    fake_client = MagicMock()
    fake_client.get_market_snapshot.return_value = {"results": {}}

    with _PatchedJob(watchlist, effective_limit=360) as job, patch(
        "rag_b3.ingestion.hg_brasil.job.HgBrasilClient", return_value=fake_client
    ):
        run_hg_brasil_ingestion(_settings(), conn=MagicMock())

    job.upsert_daily_close_mock.assert_not_called()


def test_quota_exhausted_mid_loop_marks_remaining_as_skipped():
    watchlist = _watchlist("PETR4", "VALE3", "ITUB4")
    fake_client = MagicMock()
    fake_client.get_market_snapshot.return_value = {"results": {}}
    fake_client.get_stock_price.side_effect = [
        {"results": {"PETR4": {"symbol": "PETR4", "price": 1.0}}},
        QuotaExceededError("no budget left"),
    ]

    with _PatchedJob(watchlist, effective_limit=360) as job, patch(
        "rag_b3.ingestion.hg_brasil.job.HgBrasilClient", return_value=fake_client
    ):
        summary = run_hg_brasil_ingestion(_settings(), conn=MagicMock())

    assert summary["succeeded"] == 2  # snapshot + PETR4
    assert summary["skipped_quota"] == ["VALE3", "ITUB4"]
    job.tracker_instance.finish.assert_called_once()
    finish_args = job.tracker_instance.finish.call_args.args
    assert finish_args[2] == "partial_success"


def test_ticker_error_does_not_stop_the_loop():
    watchlist = _watchlist("PETR4", "XXXX0", "VALE3")
    fake_client = MagicMock()
    fake_client.get_market_snapshot.return_value = {"results": {}}
    fake_client.get_stock_price.side_effect = [
        {"results": {"PETR4": {"symbol": "PETR4", "price": 1.0}}},
        HgBrasilTickerError("INVALID_TICKER", "ticker inválido"),
        {"results": {"VALE3": {"symbol": "VALE3", "price": 2.0}}},
    ]

    with _PatchedJob(watchlist, effective_limit=360), patch(
        "rag_b3.ingestion.hg_brasil.job.HgBrasilClient", return_value=fake_client
    ):
        summary = run_hg_brasil_ingestion(_settings(), conn=MagicMock())

    assert summary["succeeded"] == 3  # snapshot + PETR4 + VALE3
    assert summary["failed"] == 1  # XXXX0
    assert summary["skipped_quota"] == []


def test_plan_restricted_stops_ticker_loop_immediately():
    # Descoberto ao validar contra a API real: /finance/stock_price é
    # bloqueado inteiramente no plano free — insistir nos próximos tickers
    # só desperdiçaria cota, então o loop deve parar no primeiro sinal.
    watchlist = _watchlist("PETR4", "VALE3", "ITUB4")
    fake_client = MagicMock()
    fake_client.get_market_snapshot.return_value = {"results": {}}
    fake_client.get_stock_price.side_effect = HgBrasilPlanRestrictedError(
        "PLAN_RESTRICTED", "Esta consulta necessita do plano Member Premium ou superior."
    )

    with _PatchedJob(watchlist, effective_limit=360) as job, patch(
        "rag_b3.ingestion.hg_brasil.job.HgBrasilClient", return_value=fake_client
    ):
        summary = run_hg_brasil_ingestion(_settings(), conn=MagicMock())

    assert summary["succeeded"] == 1  # só o snapshot
    assert summary["skipped_plan_restricted"] == ["PETR4", "VALE3", "ITUB4"]
    assert fake_client.get_stock_price.call_count == 1  # não insistiu nos outros
    finish_args = job.tracker_instance.finish.call_args.args
    assert finish_args[2] == "partial_success"


def test_preflight_abort_never_calls_client():
    watchlist = _watchlist("PETR4", "VALE3")
    with _PatchedJob(watchlist, effective_limit=0) as job, patch(
        "rag_b3.ingestion.hg_brasil.job.HgBrasilClient"
    ) as client_cls:
        summary = run_hg_brasil_ingestion(_settings(on_insufficient_budget="abort"), conn=MagicMock())

    client_cls.assert_not_called()
    assert summary["succeeded"] == 0
    finish_args = job.tracker_instance.finish.call_args.args
    assert finish_args[2] == "aborted_insufficient_budget"


def test_full_success_when_everything_works():
    watchlist = _watchlist("PETR4", "VALE3")
    fake_client = MagicMock()
    fake_client.get_market_snapshot.return_value = {"results": {}}
    fake_client.get_stock_price.side_effect = [
        {"results": {"PETR4": {"symbol": "PETR4", "price": 1.0}}},
        {"results": {"VALE3": {"symbol": "VALE3", "price": 2.0}}},
    ]

    with _PatchedJob(watchlist, effective_limit=360) as job, patch(
        "rag_b3.ingestion.hg_brasil.job.HgBrasilClient", return_value=fake_client
    ):
        summary = run_hg_brasil_ingestion(_settings(), conn=MagicMock())

    assert summary == {
        "requested": 3,
        "succeeded": 3,
        "failed": 0,
        "skipped_quota": [],
        "skipped_plan_restricted": [],
    }
    finish_args = job.tracker_instance.finish.call_args.args
    assert finish_args[2] == "success"
