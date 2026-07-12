from pathlib import Path

from rag_b3.config.watchlist import load_watchlist

REPO_WATCHLIST = Path(__file__).parent.parent.parent / "config" / "watchlist.yaml"


def test_load_real_watchlist_file():
    # Desativada de propósito (ver comentário no topo de watchlist.yaml):
    # /finance/stock_price é bloqueado no plano free da HG Brasil para
    # qualquer símbolo, então a watchlist real fica vazia até upgrade de
    # plano ou troca de fonte para cotação por papel individual.
    tickers = load_watchlist(REPO_WATCHLIST)
    assert tickers == []


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
