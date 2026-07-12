"""Retrieval textual sobre `cvm_feed_item` via busca lexical do Postgres
(`tsvector`/`plainto_tsquery`), sem embedding. Decisão registrada em
constitution.md: com ~60 itens no total, a maioria das perguntas é resolvida
por recência (feed + data), não por similaridade semântica — busca vetorial
fica para quando o volume justificar o custo/infra extra."""

from psycopg import Connection

from rag_b3.retrieval.models import CvmFeedResult

FEED_KEYS = (
    "decisoes",
    "legislacao",
    "sancionadores",
    "despachos",
    "audiencias",
    "informativos_colegiado",
)

_COLUMNS = "feed_key, title, summary, link, published_at"


def _row_to_result(row) -> CvmFeedResult:
    return CvmFeedResult(
        feed_key=row[0], title=row[1], summary=row[2], link=row[3], published_at=row[4]
    )


def latest_by_feed(conn: Connection, feed_key: str, limit: int = 1) -> list[CvmFeedResult]:
    """Itens mais recentes de um feed — cobre a maioria das perguntas
    regulatórias ("saiu alguma decisão recente?"), que são de recência, não
    de busca semântica."""
    if feed_key not in FEED_KEYS:
        raise ValueError(f"feed_key inválido: {feed_key!r}. Válidos: {FEED_KEYS}")
    with conn.cursor() as cur:
        cur.execute(
            f"""
            select {_COLUMNS} from cvm_feed_item
            where feed_key = %s
            order by published_at desc nulls last
            limit %s
            """,
            (feed_key, limit),
        )
        rows = cur.fetchall()
    return [_row_to_result(r) for r in rows]


def search_cvm_items(
    conn: Connection, query_text: str, feed_key: str | None = None, limit: int = 5
) -> list[CvmFeedResult]:
    """Busca lexical (português) em título + resumo, ordenada por
    relevância e depois por data mais recente."""
    if feed_key is not None and feed_key not in FEED_KEYS:
        raise ValueError(f"feed_key inválido: {feed_key!r}. Válidos: {FEED_KEYS}")
    with conn.cursor() as cur:
        cur.execute(
            f"""
            select {_COLUMNS} from cvm_feed_item
            where to_tsvector('portuguese', coalesce(title, '') || ' ' || coalesce(summary, ''))
                  @@ plainto_tsquery('portuguese', %s)
                  and (%s::text is null or feed_key = %s)
            order by ts_rank(
                to_tsvector('portuguese', coalesce(title, '') || ' ' || coalesce(summary, '')),
                plainto_tsquery('portuguese', %s)
            ) desc, published_at desc nulls last
            limit %s
            """,
            (query_text, feed_key, feed_key, query_text, limit),
        )
        rows = cur.fetchall()
    return [_row_to_result(r) for r in rows]
