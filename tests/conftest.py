import json
from datetime import date
from pathlib import Path

import pytest

from rag_b3.ingestion.hg_brasil.budget_manager import QuotaExceededError

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


def load_json_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def load_text_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class InMemoryBudgetRepository:
    """Fake usado só nos testes — nunca bate no Postgres real. Replica a
    semântica atômica da função SQL reserve_hg_brasil_quota: reserva falha
    sem incrementar o contador além do effective_limit."""

    def __init__(self, effective_limit: int = 360):
        self._used: dict[date, int] = {}
        self._effective_limit = effective_limit

    def get_status(self, quota_date: date) -> tuple[int, int]:
        return self._used.get(quota_date, 0), self._effective_limit

    def reserve(self, quota_date: date, n: int) -> int:
        current = self._used.get(quota_date, 0)
        if current + n > self._effective_limit:
            raise QuotaExceededError(f"quota exceeded for {quota_date}")
        current += n
        self._used[quota_date] = current
        return current
