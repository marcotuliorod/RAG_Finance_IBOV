import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from rag_b3.ingestion.brapi.errors import BrapiAuthError, BrapiPossibleQuotaExceeded, BrapiRequestError

logger = logging.getLogger(__name__)

BASE_URL = "https://brapi.dev/api"


class _TransientError(Exception):
    """Erro de rede/servidor retentável (timeout, conexão, 5xx). Nunca usado
    para erros de aplicação (auth, cota) — retentar não ajuda nesses casos."""


class BrapiClient:
    """Cliente HTTP para a brapi.dev API (https://brapi.dev/docs/acoes).
    Diferente da HG Brasil, aceita múltiplos tickers separados por vírgula
    em uma única requisição (GET /quote/AAA,BBB,CCC) — a watchlist inteira
    é buscada de uma vez (ver job.py), sem precisar de um budget manager por
    requisição individual. PETR4/VALE3/ITUB4/MGLU3 respondem sem token; os
    demais tickers exigem token do plano free."""

    def __init__(self, token: str | None, base_url: str = BASE_URL):
        self._token = token
        self._http = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "BrapiClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get_quotes(self, symbols: list[str]) -> dict:
        """GET /quote/{símbolos separados por vírgula} — 1 requisição cobre
        a watchlist inteira."""
        return self._fetch(f"/quote/{','.join(symbols)}")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=4),
        retry=retry_if_exception_type(_TransientError),
    )
    def _fetch(self, path: str) -> dict:
        params = {"token": self._token} if self._token else {}
        try:
            response = self._http.get(path, params=params)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise _TransientError(str(exc)) from exc

        if response.status_code in (401, 403):
            raise BrapiAuthError(str(response.status_code), "Token brapi ausente ou inválido", None)
        if response.status_code == 429:
            raise BrapiPossibleQuotaExceeded(
                "HTTP_429", "Limite de requisições brapi.dev atingido", None
            )
        if response.status_code >= 500:
            raise _TransientError(f"HTTP {response.status_code}")
        if response.status_code >= 400:
            raise BrapiRequestError(
                str(response.status_code), "Requisição rejeitada pela brapi.dev", None
            )

        data = response.json()

        if isinstance(data, dict) and data.get("error"):
            raise BrapiRequestError(
                "API_ERROR", str(data.get("message", data.get("error"))), data
            )

        return data
