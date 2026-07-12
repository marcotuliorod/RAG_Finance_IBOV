from pathlib import Path

import yaml
from pydantic import BaseModel


class WatchlistTicker(BaseModel):
    symbol: str
    name: str | None = None


def load_watchlist(path: Path) -> list[WatchlistTicker]:
    """Carrega a watchlist configurável (config/watchlist.yaml).

    A ordem do arquivo é a ordem de prioridade usada pelo budget manager
    quando o orçamento de requisições não cobre a lista inteira.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    tickers = data.get("tickers", []) if data else []
    return [WatchlistTicker(**t) for t in tickers]
