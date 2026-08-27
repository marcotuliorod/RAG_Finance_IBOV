from datetime import date, datetime, timezone

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from rag_b3.ingestion.yahoo_finance.models import IbovDailyBar

BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
IBOV_SYMBOL = "%5EBVSP"  # ^BVSP URL-encoded

USER_AGENT = "Mozilla/5.0 (rag-b3-ibov-backfill/0.1; uso pessoal/pesquisa)"

# Âncora fixa do início da série, não "últimos N anos" relativo a hoje.
# Descoberta ao vivo em 2026-08-24 (migração Supabase → Postgres local):
# o parâmetro `range=10y` do chart API é relativo ao momento da chamada —
# rodar o backfill em datas diferentes produzia janelas de 10 anos
# diferentes (ex.: início em 2016-07-11 numa execução, 2016-08-24 noutra),
# quebrando qualquer teste/asserção com valor "conhecido" de início de
# série. period1/period2 explícitos (usados abaixo) mantêm granularidade
# diária mesmo em janelas longas — diferente de `range=max`, que a Yahoo
# silenciosamente reamostra para ~mensal.
SERIES_START = date(2016, 1, 1)


class YahooFinanceError(Exception):
    """Erro ao buscar ou parsear a resposta do chart API do Yahoo Finance.

    Este endpoint não é uma API oficialmente documentada/suportada pela
    Yahoo — amplamente usado (ex.: pela lib yfinance), mas sujeito a mudar
    de formato ou ficar indisponível sem aviso. Usado só para backfill
    histórico pontual, nunca no caminho de consulta de usuário."""


class _TransientError(Exception):
    """Erro de rede/servidor retentável — nunca usado para respostas
    malformadas (essas não se resolvem tentando de novo)."""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=4),
    retry=retry_if_exception_type(_TransientError),
)
def fetch_ibov_chart(
    start: date = SERIES_START, end: date | None = None, interval: str = "1d", timeout: float = 15.0
) -> dict:
    end = end or date.today()
    period1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    period2 = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp())
    try:
        response = httpx.get(
            f"{BASE_URL}/{IBOV_SYMBOL}",
            params={"period1": period1, "period2": period2, "interval": interval},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise _TransientError(str(exc)) from exc

    if response.status_code >= 500:
        raise _TransientError(f"HTTP {response.status_code}")
    if response.status_code != 200:
        raise YahooFinanceError(f"HTTP {response.status_code}: {response.text[:300]}")

    data = response.json()
    if data.get("chart", {}).get("error"):
        raise YahooFinanceError(str(data["chart"]["error"]))
    return data


def parse_ibov_chart(raw: dict) -> list[IbovDailyBar]:
    """Extrai barras diárias OHLC do payload do chart API. Dias sem `close`
    (candle do dia ainda se formando, ou gap na série) são descartados —
    não inventamos dado onde a fonte não tem."""
    try:
        result = raw["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise YahooFinanceError(f"Formato de resposta inesperado: {exc}") from exc

    bars: list[IbovDailyBar] = []
    prev_close: float | None = None
    for i, ts in enumerate(timestamps):
        close = quote.get("close", [None] * len(timestamps))[i]
        if close is None:
            continue
        trade_date = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        variation_percent = (
            (close - prev_close) / prev_close * 100 if prev_close else None
        )
        bars.append(
            IbovDailyBar(
                trade_date=trade_date,
                open=quote.get("open", [None] * len(timestamps))[i],
                high=quote.get("high", [None] * len(timestamps))[i],
                low=quote.get("low", [None] * len(timestamps))[i],
                close=close,
                volume=quote.get("volume", [None] * len(timestamps))[i] or None,
                variation_percent=variation_percent,
            )
        )
        prev_close = close
    return bars
