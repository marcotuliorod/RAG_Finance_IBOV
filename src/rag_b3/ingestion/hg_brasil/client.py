import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from rag_b3.ingestion.hg_brasil.budget_manager import BudgetManager
from rag_b3.ingestion.hg_brasil.errors import (
    HgBrasilPlanRestrictedError,
    HgBrasilPossibleQuotaExceeded,
    error_from_code,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hgbrasil.com/finance"


class _TransientError(Exception):
    """Erro de rede/servidor retentável (timeout, conexão, 5xx). Nunca usado
    para erros de aplicação documentados — retentar INVALID_TICKER só
    desperdiça cota."""


class HgBrasilClient:
    """Cliente HTTP para a HG Brasil Finance API. Só deve ser instanciado
    dentro do job batch de ingestão (ingestion/hg_brasil/job.py) — nunca em
    caminho de consulta de usuário, já que os dados têm 15min-1h de atraso e
    o orçamento diário é escasso (400 req/dia no plano free)."""

    def __init__(self, api_key: str, budget: BudgetManager, base_url: str = BASE_URL):
        self._api_key = api_key
        self._budget = budget
        self._http = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "HgBrasilClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get_market_snapshot(self) -> dict:
        """GET /finance — 1 requisição, retorna currencies/stocks/bitcoin/taxes."""
        return self._fetch("", {})

    def get_stock_price(self, symbol: str) -> dict:
        """GET /finance/stock_price?symbol=... — 1 requisição por ticker
        (plano free não permite múltiplos símbolos por requisição)."""
        return self._fetch("/stock_price", {"symbol": symbol})

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=4),
        retry=retry_if_exception_type(_TransientError),
    )
    def _fetch(self, path: str, params: dict) -> dict:
        # Reserva ANTES da chamada HTTP (pessimista) — cada tentativa de
        # retry reserva de novo, já que a HG Brasil não documenta o que
        # acontece ao exceder a cota.
        self._budget.reserve(1)

        try:
            response = self._http.get(path, params={**params, "key": self._api_key})
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise _TransientError(str(exc)) from exc

        if response.status_code == 429:
            raise HgBrasilPossibleQuotaExceeded(
                "HTTP_429",
                "Possível limite de cota atingido (comportamento não documentado pela HG Brasil)",
                None,
            )
        if response.status_code >= 500:
            raise _TransientError(f"HTTP {response.status_code}")

        data = response.json()

        results = data.get("results")
        if isinstance(results, dict) and results.get("error"):
            raise HgBrasilPlanRestrictedError(
                "PLAN_RESTRICTED", results.get("message", ""), data
            )

        errors = data.get("errors")
        if errors:
            err = errors[0]
            code = err.get("code", "UNKNOWN")
            message = err.get("message", "")
            text_blob = f"{code} {message}".lower()
            if "quota" in text_blob or "limit" in text_blob:
                raise HgBrasilPossibleQuotaExceeded(code, message, data)
            raise error_from_code(code, message, data)

        return data
