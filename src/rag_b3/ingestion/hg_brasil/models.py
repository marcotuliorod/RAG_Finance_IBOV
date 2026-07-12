from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StockPrice(BaseModel):
    """Campos documentados de /finance/stock_price. Documentação pública é
    incompleta — extra="allow" evita que um campo novo/desconhecido quebre o
    parsing; o raw_response completo é sempre persistido à parte de qualquer
    forma (ver repository.py)."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    name: str | None = None
    kind: str | None = None
    price: float | None = None
    change_percent: float | None = None
    change_price: float | None = None
    volume: int | None = None
    market_cap: float | None = None
    currency: str | None = None
    region: str | None = None
    market_time: str | None = None
    updated_at: datetime | None = None


class MarketSnapshot(BaseModel):
    """Extração best-effort dos campos do endpoint principal /finance
    (índices/moedas/taxas). Campos None quando a extração falha — o
    raw_response completo nunca é perdido (ver repository.py)."""

    ibovespa_points: float | None = None
    ifix_points: float | None = None
    usd_brl: float | None = None
    cdi_rate: float | None = None
    selic_rate: float | None = None
