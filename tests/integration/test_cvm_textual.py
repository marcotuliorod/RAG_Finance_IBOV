"""Testes de integração contra o Postgres local (Docker) já populado pelos
60 itens reais ingeridos pelos 6 feeds CVM (ver test_ibov_numeric.py para o
mesmo padrão de fixture)."""

import pytest

from rag_b3.retrieval.cvm_textual import FEED_KEYS, latest_by_feed, search_cvm_items

pytestmark = pytest.mark.integration


def test_latest_by_feed_returns_most_recent_item_for_each_feed(conn):
    for feed_key in FEED_KEYS:
        items = latest_by_feed(conn, feed_key, limit=1)
        assert len(items) == 1
        assert items[0].feed_key == feed_key


def test_latest_by_feed_respects_limit(conn):
    items = latest_by_feed(conn, "legislacao", limit=3)
    assert len(items) == 3
    published_dates = [item.published_at for item in items]
    assert published_dates == sorted(published_dates, reverse=True)


def test_latest_by_feed_rejects_invalid_feed_key(conn):
    with pytest.raises(ValueError):
        latest_by_feed(conn, "noticias_mercado", limit=1)


def test_search_cvm_items_finds_real_resolucao_items(conn):
    results = search_cvm_items(conn, "resolução", feed_key="legislacao", limit=5)
    assert len(results) > 0
    assert all(r.feed_key == "legislacao" for r in results)


def test_search_cvm_items_no_match_returns_empty(conn):
    results = search_cvm_items(conn, "criptomoeda inexistente xyzabc", limit=5)
    assert results == []


def test_search_cvm_items_rejects_invalid_feed_key(conn):
    with pytest.raises(ValueError):
        search_cvm_items(conn, "resolução", feed_key="noticias_mercado")
