from datetime import date

from psycopg import Connection

from rag_b3.query.errors import InsufficientDataError
from rag_b3.query.models import ExtremeResult, IbovBar, PeriodSummary, VariationResult

_BAR_COLUMNS = "trade_date, open, high, low, close, volume, variation_percent, source"


def _row_to_bar(row) -> IbovBar:
    return IbovBar(
        trade_date=row[0],
        open=row[1],
        high=row[2],
        low=row[3],
        close=row[4],
        volume=row[5],
        variation_percent=row[6],
        source=row[7],
    )


def get_bar_on_or_before(conn: Connection, target_date: date) -> IbovBar | None:
    """Pregão em `target_date`, ou o pregão anterior mais próximo (fins de
    semana/feriados não têm linha na série)."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            select {_BAR_COLUMNS} from ibov_daily_history
            where trade_date <= %s order by trade_date desc limit 1
            """,
            (target_date,),
        )
        row = cur.fetchone()
        return _row_to_bar(row) if row else None


def _series_bounds_hint(conn: Connection) -> str:
    """Texto com os limites reais da série, para embutir nas mensagens de
    `InsufficientDataError` — sem isso o LLM tende a "advinhar"/citar de
    memória a data de início da série em vez de basear a resposta só no que
    a ferramenta retornou (achado da avaliação de faithfulness)."""
    with conn.cursor() as cur:
        cur.execute("select min(trade_date), max(trade_date) from ibov_daily_history")
        row = cur.fetchone()
    if row is None or row[0] is None:
        return "nenhum dado disponível na série"
    return f"série disponível de {row[0]} a {row[1]}"


def get_latest_bar(conn: Connection) -> IbovBar | None:
    with conn.cursor() as cur:
        cur.execute(f"select {_BAR_COLUMNS} from ibov_daily_history order by trade_date desc limit 1")
        row = cur.fetchone()
        return _row_to_bar(row) if row else None


def variation_between(conn: Connection, start_date: date, end_date: date) -> VariationResult:
    """Variação entre dois pregões — usa o pregão mais próximo anterior a
    cada data se ela cair em fim de semana/feriado."""
    if start_date > end_date:
        raise ValueError("start_date deve ser <= end_date")
    start_bar = get_bar_on_or_before(conn, start_date)
    end_bar = get_bar_on_or_before(conn, end_date)
    if start_bar is None or end_bar is None:
        raise InsufficientDataError(
            f"Sem dado histórico suficiente entre {start_date} e {end_date} "
            f"({_series_bounds_hint(conn)})"
        )
    variation_points = end_bar.close - start_bar.close
    variation_percent = variation_points / start_bar.close * 100
    return VariationResult(
        start=start_bar,
        end=end_bar,
        variation_percent=variation_percent,
        variation_points=variation_points,
    )


def variation_last_n_trading_days(
    conn: Connection, n: int, as_of: date | None = None
) -> VariationResult:
    """Variação nos últimos N PREGÕES (não N dias corridos), terminando em
    `as_of` (default: pregão mais recente disponível na série)."""
    if n <= 0:
        raise ValueError("n deve ser positivo")
    end_bar = get_bar_on_or_before(conn, as_of) if as_of else get_latest_bar(conn)
    if end_bar is None:
        raise InsufficientDataError("Sem dado histórico disponível")

    with conn.cursor() as cur:
        cur.execute(
            f"""
            select {_BAR_COLUMNS} from ibov_daily_history
            where trade_date <= %s order by trade_date desc offset %s limit 1
            """,
            (end_bar.trade_date, n),
        )
        row = cur.fetchone()
    if row is None:
        raise InsufficientDataError(
            f"Não há {n} pregões de histórico disponíveis antes de {end_bar.trade_date} "
            f"({_series_bounds_hint(conn)})"
        )
    start_bar = _row_to_bar(row)
    variation_points = end_bar.close - start_bar.close
    variation_percent = variation_points / start_bar.close * 100
    return VariationResult(
        start=start_bar,
        end=end_bar,
        variation_percent=variation_percent,
        variation_points=variation_points,
    )


def extreme_between(conn: Connection, start_date: date, end_date: date, kind: str) -> ExtremeResult:
    if kind not in ("max", "min"):
        raise ValueError("kind deve ser 'max' ou 'min'")
    order = "desc" if kind == "max" else "asc"
    with conn.cursor() as cur:
        cur.execute(
            f"""
            select {_BAR_COLUMNS} from ibov_daily_history
            where trade_date between %s and %s
            order by close {order} limit 1
            """,
            (start_date, end_date),
        )
        row = cur.fetchone()
    if row is None:
        raise InsufficientDataError(
            f"Sem dado histórico entre {start_date} e {end_date} ({_series_bounds_hint(conn)})"
        )
    return ExtremeResult(bar=_row_to_bar(row), kind=kind)


def all_time_high(conn: Connection) -> ExtremeResult:
    with conn.cursor() as cur:
        cur.execute(f"select {_BAR_COLUMNS} from ibov_daily_history order by close desc limit 1")
        row = cur.fetchone()
    if row is None:
        raise InsufficientDataError("Sem dado histórico disponível")
    return ExtremeResult(bar=_row_to_bar(row), kind="max")


def period_summary(conn: Connection, start_date: date, end_date: date) -> PeriodSummary:
    """Resumo agregado do período: variação, máxima/mínima e média —
    resolvido inteiramente por SQL, nunca por cálculo do LLM (RF-06)."""
    if start_date > end_date:
        raise ValueError("start_date deve ser <= end_date")
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*), avg(close), max(close), min(close)
            from ibov_daily_history where trade_date between %s and %s
            """,
            (start_date, end_date),
        )
        count, avg_close, max_close, min_close = cur.fetchone()
    if not count:
        raise InsufficientDataError(
            f"Sem dado histórico entre {start_date} e {end_date} ({_series_bounds_hint(conn)})"
        )

    variation = variation_between(conn, start_date, end_date)
    max_result = extreme_between(conn, start_date, end_date, "max")
    min_result = extreme_between(conn, start_date, end_date, "min")
    return PeriodSummary(
        start_date=start_date,
        end_date=end_date,
        trading_days=count,
        variation_percent=variation.variation_percent,
        max_close=float(max_close),
        max_close_date=max_result.bar.trade_date,
        min_close=float(min_close),
        min_close_date=min_result.bar.trade_date,
        average_close=float(avg_close),
    )


def compare_period_summaries(
    conn: Connection, period_a: dict, period_b: dict
) -> dict:
    """Compara dois períodos e diz qual teve melhor desempenho — resolvido
    inteiramente por SQL/Python determinístico, nunca por comparação "de
    cabeça" do LLM (RF-06). `period_a`/`period_b` têm chaves `start_date`
    e `end_date`."""
    summary_a = period_summary(conn, period_a["start_date"], period_a["end_date"])
    summary_b = period_summary(conn, period_b["start_date"], period_b["end_date"])
    melhor = "a" if summary_a.variation_percent > summary_b.variation_percent else "b"
    diferenca_pp = abs(summary_a.variation_percent - summary_b.variation_percent)
    return {
        "summary_a": summary_a,
        "summary_b": summary_b,
        "melhor": melhor,
        "diferenca_pp": diferenca_pp,
    }
