"""Ferramentas expostas ao Claude via tool-use. Todo cálculo numérico e toda
busca textual passam por aqui — o LLM nunca calcula variação/comparação
"de cabeça" (RF-06) nem inventa conteúdo da CVM não presente no feed."""

from datetime import date

from psycopg import Connection
from pydantic import BaseModel

from rag_b3.query import ibov_numeric
from rag_b3.query.errors import InsufficientDataError
from rag_b3.retrieval import cvm_textual

TOOL_SPECS = [
    {
        "name": "ibov_latest_bar",
        "description": "Retorna o pregão mais recente do Ibovespa disponível na série "
        "histórica (data, fechamento, variação do dia).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ibov_variation_between",
        "description": "Variação do Ibovespa entre duas datas (usa o pregão mais próximo "
        "anterior se a data cair em fim de semana/feriado).",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "ibov_variation_last_n_trading_days",
        "description": "Variação do Ibovespa nos últimos N pregões (não N dias corridos), "
        "terminando no pregão mais recente ou em `as_of` se informado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer"},
                "as_of": {"type": "string", "format": "date"},
            },
            "required": ["n"],
        },
    },
    {
        "name": "ibov_extreme_between",
        "description": "Máxima ou mínima do Ibovespa (fechamento) entre duas datas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
                "kind": {"type": "string", "enum": ["max", "min"]},
            },
            "required": ["start_date", "end_date", "kind"],
        },
    },
    {
        "name": "ibov_all_time_high",
        "description": "Máxima histórica do Ibovespa em toda a série disponível "
        "(desde 2016-07-11).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ibov_period_summary",
        "description": "Resumo agregado de um período: variação, máxima, mínima e média "
        "de fechamento.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "ibov_compare_periods",
        "description": "Compara o desempenho do Ibovespa entre dois períodos e diz qual "
        "foi melhor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period_a_start": {"type": "string", "format": "date"},
                "period_a_end": {"type": "string", "format": "date"},
                "period_b_start": {"type": "string", "format": "date"},
                "period_b_end": {"type": "string", "format": "date"},
            },
            "required": ["period_a_start", "period_a_end", "period_b_start", "period_b_end"],
        },
    },
    {
        "name": "cvm_latest_by_feed",
        "description": "Itens mais recentes de um feed regulatório da CVM. feed_key deve "
        f"ser um de: {', '.join(cvm_textual.FEED_KEYS)}.",
        "input_schema": {
            "type": "object",
            "properties": {
                "feed_key": {"type": "string", "enum": list(cvm_textual.FEED_KEYS)},
                "limit": {"type": "integer"},
            },
            "required": ["feed_key"],
        },
    },
    {
        "name": "cvm_search",
        "description": "Busca por palavra-chave (português) em título/resumo dos itens "
        "regulatórios da CVM já ingeridos, opcionalmente filtrando por feed_key.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query_text": {"type": "string"},
                "feed_key": {"type": "string", "enum": list(cvm_textual.FEED_KEYS)},
                "limit": {"type": "integer"},
            },
            "required": ["query_text"],
        },
    },
]


def _serialize(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    return obj


def execute_tool(conn: Connection, name: str, tool_input: dict) -> dict:
    """Executa a ferramenta pedida pelo Claude e devolve um dict pronto para
    virar JSON no tool_result. Erros de dado insuficiente/entrada inválida
    viram `{"error": ...}` em vez de propagar exceção — é o LLM quem precisa
    ver o erro para responder "informação insuficiente" (RF-07)."""
    try:
        if name == "ibov_latest_bar":
            result = ibov_numeric.get_latest_bar(conn)
        elif name == "ibov_variation_between":
            result = ibov_numeric.variation_between(
                conn,
                date.fromisoformat(tool_input["start_date"]),
                date.fromisoformat(tool_input["end_date"]),
            )
        elif name == "ibov_variation_last_n_trading_days":
            as_of = tool_input.get("as_of")
            result = ibov_numeric.variation_last_n_trading_days(
                conn,
                n=tool_input["n"],
                as_of=date.fromisoformat(as_of) if as_of else None,
            )
        elif name == "ibov_extreme_between":
            result = ibov_numeric.extreme_between(
                conn,
                date.fromisoformat(tool_input["start_date"]),
                date.fromisoformat(tool_input["end_date"]),
                tool_input["kind"],
            )
        elif name == "ibov_all_time_high":
            result = ibov_numeric.all_time_high(conn)
        elif name == "ibov_period_summary":
            result = ibov_numeric.period_summary(
                conn,
                date.fromisoformat(tool_input["start_date"]),
                date.fromisoformat(tool_input["end_date"]),
            )
        elif name == "ibov_compare_periods":
            result = ibov_numeric.compare_period_summaries(
                conn,
                period_a={
                    "start_date": date.fromisoformat(tool_input["period_a_start"]),
                    "end_date": date.fromisoformat(tool_input["period_a_end"]),
                },
                period_b={
                    "start_date": date.fromisoformat(tool_input["period_b_start"]),
                    "end_date": date.fromisoformat(tool_input["period_b_end"]),
                },
            )
        elif name == "cvm_latest_by_feed":
            result = cvm_textual.latest_by_feed(
                conn, tool_input["feed_key"], tool_input.get("limit", 1)
            )
        elif name == "cvm_search":
            result = cvm_textual.search_cvm_items(
                conn,
                tool_input["query_text"],
                tool_input.get("feed_key"),
                tool_input.get("limit", 5),
            )
        else:
            return {"error": f"ferramenta desconhecida: {name}"}
    except (InsufficientDataError, ValueError) as exc:
        return {"error": str(exc)}

    if result is None:
        return {"error": "sem dado disponível"}
    return _serialize(result)
