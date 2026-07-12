import time_machine

from rag_b3.ingestion.hg_brasil.budget_manager import BudgetManager, QuotaExceededError
from tests.conftest import InMemoryBudgetRepository


def test_effective_limit_math_matches_400_times_090():
    # daily_limit=400, safety_margin=0.90 -> effective_limit=360 (ver
    # db/migrations/0003_hg_brasil_quota_control.sql: floor(400 * 0.90))
    repo = InMemoryBudgetRepository(effective_limit=360)
    manager = BudgetManager(repo)
    assert manager.remaining() == 360


def test_reserve_increments_and_remaining_decreases():
    repo = InMemoryBudgetRepository(effective_limit=360)
    manager = BudgetManager(repo)
    manager.reserve(21)
    assert manager.remaining() == 339


def test_quota_exceeded_does_not_increment_past_limit():
    repo = InMemoryBudgetRepository(effective_limit=5)
    manager = BudgetManager(repo)
    manager.reserve(5)
    assert manager.remaining() == 0
    try:
        manager.reserve(1)
        raised = False
    except QuotaExceededError:
        raised = True
    assert raised
    # o contador não deve ter incrementado além do limite
    assert manager.remaining() == 0


def test_reset_is_per_day_america_sao_paulo():
    repo = InMemoryBudgetRepository(effective_limit=360)
    manager = BudgetManager(repo)

    with time_machine.travel("2026-07-10 12:00:00-03:00"):
        manager.reserve(100)
        assert manager.remaining() == 260

    # dia seguinte: novo bucket, orçamento cheio de novo
    with time_machine.travel("2026-07-11 08:00:00-03:00"):
        assert manager.remaining() == 360


def test_preflight_full_when_estimated_within_budget():
    repo = InMemoryBudgetRepository(effective_limit=360)
    manager = BudgetManager(repo)
    result = manager.preflight(estimated_calls=21)
    assert result.mode == "full"
    assert result.allowed_calls == 21


def test_preflight_partial_default_when_insufficient():
    repo = InMemoryBudgetRepository(effective_limit=10)
    manager = BudgetManager(repo, on_insufficient_budget="partial")
    result = manager.preflight(estimated_calls=21)
    assert result.mode == "partial"
    assert result.allowed_calls == 10


def test_preflight_abort_when_configured():
    repo = InMemoryBudgetRepository(effective_limit=10)
    manager = BudgetManager(repo, on_insufficient_budget="abort")
    result = manager.preflight(estimated_calls=21)
    assert result.mode == "abort"
    assert result.allowed_calls == 0
