from datetime import date

from pydantic import BaseModel


class IbovDailyBar(BaseModel):
    """Barra diária OHLC do Ibovespa. `volume` costuma vir None/0 — um
    índice não tem volume próprio (seria o volume financeiro total do
    pregão B3, dado institucional pago, fora do escopo atual)."""

    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int | None = None
    variation_percent: float | None = None
