from pathlib import Path

from rag_b3.config.watchlist import load_watchlist

REPO_WATCHLIST = Path(__file__).parent.parent.parent / "config" / "watchlist.yaml"


def test_load_real_watchlist_file():
    # Reativada em 2026-08-24 via brapi.dev (ver comentário no topo de
    # watchlist.yaml) — HG Brasil free segue bloqueando
    # /finance/stock_price, mas a cotação por ticker agora vem do job brapi
    # (rag_b3.ingestion.brapi), então a watchlist volta a ter os 20 tickers
    # de prioridade.
    tickers = load_watchlist(REPO_WATCHLIST)
    assert len(tickers) == 20
    assert tickers[0].symbol == "PETR4"


def test_load_watchlist_from_tmp_file(tmp_path):
    content = """
tickers:
  - symbol: AAAA1
    name: Empresa Teste
  - symbol: BBBB2
"""
    path = tmp_path / "watchlist.yaml"
    path.write_text(content, encoding="utf-8")
    tickers = load_watchlist(path)
    assert [t.symbol for t in tickers] == ["AAAA1", "BBBB2"]
    assert tickers[0].name == "Empresa Teste"
    assert tickers[1].name is None
