from dataclasses import dataclass
from datetime import date
from typing import Protocol

from psycopg import Connection
from psycopg.errors import RaiseException

from rag_b3.common.time_utils import today_sao_paulo


class QuotaExceededError(Exception):
    """Levantada quando não há orçamento restante — nunca deixar estourar 400/dia."""


class BudgetRepository(Protocol):
    """Interface do repositório de cota — permite um fake in-memory nos
    testes unitários (nunca bater no Postgres real nos testes)."""

    def get_status(self, quota_date: date) -> tuple[int, int]:
        """Retorna (requests_used, effective_limit) do dia informado."""
        ...

    def reserve(self, quota_date: date, n: int) -> int:
        """Reserva n requisições atomicamente. Retorna o novo total usado.
        Levanta QuotaExceededError se n excederia o effective_limit."""
        ...


class PostgresBudgetRepository:
    """Implementação real — chama a função SQL reserve_hg_brasil_quota, que
    faz a reserva atômica em uma única transação (ver
    db/migrations/0003_hg_brasil_quota_control.sql)."""

    def __init__(self, conn: Connection):
        self._conn = conn

    def get_status(self, quota_date: date) -> tuple[int, int]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                insert into hg_brasil_quota_control (quota_date) values (%s)
                on conflict (quota_date) do nothing
                """,
                (quota_date,),
            )
            cur.execute(
                "select requests_used, effective_limit from hg_brasil_quota_control"
                " where quota_date = %s",
                (quota_date,),
            )
            row = cur.fetchone()
            assert row is not None
            return row[0], row[1]

    def reserve(self, quota_date: date, n: int) -> int:
        try:
            with self._conn.cursor() as cur:
                cur.execute("select reserve_hg_brasil_quota(%s, %s)", (quota_date, n))
                row = cur.fetchone()
                assert row is not None
                return row[0]
        except RaiseException as exc:
            if "QUOTA_EXCEEDED" in str(exc):
                raise QuotaExceededError(str(exc)) from exc
            raise


@dataclass
class PreflightResult:
    mode: str  # "full" | "partial" | "abort"
    allowed_calls: int
    remaining_before: int
    estimated_calls: int


class BudgetManager:
    """A "inteligência de cota": garante que o uso diário da HG Brasil nunca
    ultrapasse o orçamento seguro (effective_limit = daily_limit * safety_margin,
    calculado no banco). Reserva é pessimista (antes da chamada HTTP), porque
    a HG Brasil não documenta o comportamento de "cota excedida" — mais
    seguro contar o slot antes de saber o resultado do que arriscar."""

    def __init__(self, repo: BudgetRepository, on_insufficient_budget: str = "partial"):
        if on_insufficient_budget not in ("partial", "abort"):
            raise ValueError("on_insufficient_budget deve ser 'partial' ou 'abort'")
        self._repo = repo
        self._on_insufficient_budget = on_insufficient_budget

    def remaining(self) -> int:
        used, effective_limit = self._repo.get_status(today_sao_paulo())
        return max(effective_limit - used, 0)

    def reserve(self, n: int = 1) -> int:
        return self._repo.reserve(today_sao_paulo(), n)

    def preflight(self, estimated_calls: int) -> PreflightResult:
        remaining_before = self.remaining()
        if estimated_calls <= remaining_before:
            return PreflightResult("full", estimated_calls, remaining_before, estimated_calls)
        if self._on_insufficient_budget == "abort":
            return PreflightResult("abort", 0, remaining_before, estimated_calls)
        return PreflightResult("partial", remaining_before, remaining_before, estimated_calls)
