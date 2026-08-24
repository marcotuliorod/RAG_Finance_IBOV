from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StockQuote(BaseModel):
    """Campos usados de /api/quote (brapi.dev, https://brapi.dev/docs/acoes).
    Documentação de terceiros — extra="allow" evita que um campo novo/
    desconhecido quebre o parsing; o raw_response completo (a resposta em
    lote da watchlist inteira) é sempre persistido à parte (ver
    repository.py)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    symbol: str
    short_name: str | None = Field(default=None, alias="shortName")
    long_name: str | None = Field(default=None, alias="longName")
    price: float | None = Field(default=None, alias="regularMarketPrice")
    change_percent: float | None = Field(default=None, alias="regularMarketChangePercent")
    change_price: float | None = Field(default=None, alias="regularMarketChange")
    volume: int | None = Field(default=None, alias="regularMarketVolume")
    market_cap: float | None = Field(default=None, alias="marketCap")
    currency: str | None = None
    api_updated_at: datetime | None = Field(default=None, alias="regularMarketTime")
