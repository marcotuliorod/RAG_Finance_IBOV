"""Testes de integração contra o Postgres local (Docker) já populado pelo
backfill real do Yahoo Finance + ingestão diária do HG Brasil — não roda no
CI padrão (ver pyproject.toml: addopts = "-m 'not integration'").

Requer o container `rag-b3-postgres` no ar com as migrations aplicadas
(ver comandos usados durante o desenvolvimento, ou TEST_DATABASE_URL
apontando para outra instância com o mesmo schema/dado)."""

from datetime import date

import pytest

from rag_b3.query.errors import InsufficientDataError
from rag_b3.query.ibov_numeric import (
    all_time_high,
    extreme_between,
    get_bar_on_or_before,
    get_latest_bar,
    period_summary,
    variation_between,
    variation_last_n_trading_days,
)

pytestmark = pytest.mark.integration


def test_get_latest_bar_returns_most_recent_trade_date(conn):
    bar = get_latest_bar(conn)
    assert bar is not None
    assert bar.trade_date >= date(2026, 7, 10)


def test_get_bar_on_or_before_falls_back_to_prior_trading_day(conn):
    # 2026-07-12 é domingo — não deve haver linha para essa data
    bar = get_bar_on_or_before(conn, date(2026, 7, 12))
    assert bar is not None
    assert bar.trade_date <= date(2026, 7, 12)


def test_get_bar_on_or_before_before_series_start_returns_none(conn):
    bar = get_bar_on_or_before(conn, date(2000, 1, 1))
    assert bar is None


def test_variation_between_known_dates(conn):
    # 2016-07-11 (início da série, close=53960) até 2026-04-14 (máxima
    # histórica, close=198657) — valores confirmados via psql direto.
    result = variation_between(conn, date(2016, 7, 11), date(2026, 4, 14))
    assert result.start.close == pytest.approx(53960, rel=1e-3)
    assert result.end.close == pytest.approx(198657, rel=1e-3)
    assert result.variation_points == pytest.approx(198657 - 53960, rel=1e-3)
    assert result.variation_percent > 0


def test_variation_between_raises_for_period_before_series_start(conn):
    with pytest.raises(InsufficientDataError):
        variation_between(conn, date(1990, 1, 1), date(1995, 1, 1))


def test_variation_last_n_trading_days(conn):
    result = variation_last_n_trading_days(conn, 30)
    assert result.start.trade_date < result.end.trade_date
    # 30 pregões cobrem bem menos que 30 dias corridos de calendário
    assert (result.end.trade_date - result.start.trade_date).days <= 45


def test_all_time_high_matches_known_value(conn):
    result = all_time_high(conn)
    assert result.kind == "max"
    assert result.bar.trade_date == date(2026, 4, 14)
    assert result.bar.close == pytest.approx(198657, rel=1e-3)


def test_extreme_between_min_matches_known_series_start(conn):
    result = extreme_between(conn, date(2016, 1, 1), date(2017, 1, 1), "min")
    assert result.kind == "min"
    assert result.bar.close == pytest.approx(53960, rel=1e-3)


def test_extreme_between_invalid_kind_raises(conn):
    with pytest.raises(ValueError):
        extreme_between(conn, date(2020, 1, 1), date(2020, 2, 1), "median")


def test_period_summary_internally_consistent(conn):
    summary = period_summary(conn, date(2016, 7, 11), date(2026, 4, 14))
    assert summary.trading_days > 2000
    assert summary.max_close == pytest.approx(198657, rel=1e-3)
    assert summary.max_close_date == date(2026, 4, 14)
    assert summary.min_close == pytest.approx(53960, rel=1e-3)
    assert summary.min_close_date == date(2016, 7, 11)
    assert summary.min_close <= summary.average_close <= summary.max_close


def test_period_summary_raises_when_no_data_in_range(conn):
    with pytest.raises(InsufficientDataError):
        period_summary(conn, date(1990, 1, 1), date(1990, 6, 1))
