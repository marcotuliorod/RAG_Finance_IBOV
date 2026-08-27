"""Roda os casos `sql_numerico*` do golden dataset contra a camada de
consulta real (rag_b3.query.ibov_numeric) e o dado real do backfill —
funciona como o embrião do "eval gate" descrito no PRD/constitution: se um
valor esperado deixar de bater, algo mudou no dado ou na lógica de cálculo
e merece investigação antes de seguir para a camada de geração.

Casos textuais/multi-hop/adversariais (sem `resolver`) não são verificados
aqui — servem de referência para quando a camada de geração existir."""

from datetime import date

import pytest

from rag_b3.query import ibov_numeric
from rag_b3.query.errors import InsufficientDataError
from tests.integration._golden_dataset import load_cases

pytestmark = pytest.mark.integration


def _normalize_kwargs(kwargs: dict) -> dict:
    """Converte strings ISO em `date` para chaves terminadas em `_date`,
    inclusive dentro de dicts aninhados (ex.: period_a/period_b)."""
    normalized = {}
    for key, value in kwargs.items():
        if isinstance(value, str) and key.endswith("_date"):
            normalized[key] = date.fromisoformat(value)
        elif isinstance(value, dict):
            normalized[key] = _normalize_kwargs(value)
        else:
            normalized[key] = value
    return normalized


NUMERIC_CASES = [c for c in load_cases() if c.get("resolver")]


@pytest.mark.parametrize("case", NUMERIC_CASES, ids=[c["id"] for c in NUMERIC_CASES])
def test_golden_case_matches_expected_values(conn, case):
    resolver = case["resolver"]
    fn = getattr(ibov_numeric, resolver["function"])
    kwargs = _normalize_kwargs(resolver["kwargs"])
    expected = case.get("expected_values", {})

    if expected.get("raises") == "InsufficientDataError":
        with pytest.raises(InsufficientDataError):
            fn(conn, **kwargs)
        return

    result = fn(conn, **kwargs)

    if case.get("time_relative"):
        _assert_time_relative_case(conn, case, result)
        return

    for key, expected_value in expected.items():
        actual_value = _extract(result, key)
        if isinstance(expected_value, float):
            assert actual_value == pytest.approx(expected_value, abs=0.05), (
                f"caso {case['id']}, campo {key}: esperado {expected_value}, "
                f"obtido {actual_value}"
            )
        elif isinstance(expected_value, str) and _looks_like_date(expected_value):
            assert str(actual_value) == expected_value, (
                f"caso {case['id']}, campo {key}: esperado {expected_value}, "
                f"obtido {actual_value}"
            )
        else:
            assert actual_value == expected_value, (
                f"caso {case['id']}, campo {key}: esperado {expected_value}, "
                f"obtido {actual_value}"
            )


def _assert_time_relative_case(conn, case, result) -> None:
    """Casos marcados `time_relative` (ver golden_v1.json) perguntam sobre
    "os últimos N pregões" ou "a cotação mais recente" — não têm um valor
    esperado fixo, porque o fim da janela é sempre o dado mais novo
    disponível no momento em que o teste roda, que muda a cada backfill/
    ingestão diária (ver client.SERIES_START para o análogo do início da
    série, que esse SIM é fixo). Valida consistência estrutural contra uma
    consulta SQL independente, não um número congelado."""
    latest = _latest_trade_date(conn)
    end_date = result.end.trade_date if hasattr(result, "end") else result.trade_date
    assert end_date == latest, (
        f"caso {case['id']}: data final do resultado ({end_date}) não bate com o "
        f"pregão mais recente em ibov_daily_history ({latest})"
    )
    close = result.end.close if hasattr(result, "end") else result.close
    assert close > 0, f"caso {case['id']}: close não positivo ({close})"


def _latest_trade_date(conn) -> date:
    with conn.cursor() as cur:
        cur.execute("select max(trade_date) from ibov_daily_history")
        row = cur.fetchone()
        return row[0]


def _looks_like_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _extract(result, key: str):
    """Extrai um campo de um resultado que pode ser um Pydantic model
    (VariationResult, ExtremeResult, PeriodSummary...), um IbovBar
    diretamente (get_latest_bar/all_time_high) ou um dict
    (compare_period_summaries)."""
    if isinstance(result, dict):
        return result[key]
    # VariationResult: start_date/end_date apontam para result.start/end.trade_date
    if key == "start_date" and hasattr(result, "start"):
        return result.start.trade_date
    if key == "end_date" and hasattr(result, "end"):
        return result.end.trade_date
    # ExtremeResult: trade_date/close apontam para result.bar
    if key in ("trade_date", "close") and hasattr(result, "bar"):
        return getattr(result.bar, key)
    return getattr(result, key)
