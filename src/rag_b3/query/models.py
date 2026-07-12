from datetime import date

from pydantic import BaseModel


class IbovBar(BaseModel):
    trade_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None
    variation_percent: float | None
    source: str


class VariationResult(BaseModel):
    start: IbovBar
    end: IbovBar
    variation_percent: float
    variation_points: float


class ExtremeResult(BaseModel):
    bar: IbovBar
    kind: str  # "max" | "min"


class PeriodSummary(BaseModel):
    start_date: date
    end_date: date
    trading_days: int
    variation_percent: float
    max_close: float
    max_close_date: date
    min_close: float
    min_close_date: date
    average_close: float
