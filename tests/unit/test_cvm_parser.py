from rag_b3.ingestion.cvm_rss.parser import parse_entries
from tests.conftest import load_text_fixture


def test_parse_valid_feed_extracts_items_with_link_as_guid_fallback():
    content = load_text_fixture("cvm_feed_sample_decisoes.xml")
    items, bozo = parse_entries("decisoes", content)

    assert bozo is False
    assert len(items) == 2
    first = items[0]
    assert first.feed_key == "decisoes"
    # feed real não tem <guid> — dedup cai no fallback do link
    assert first.guid == "http://www.cvm.gov.br/decisoes/2025/20251203_R1.html"
    assert first.link == "http://www.cvm.gov.br/decisoes/2025/20251203_R1.html"
    assert "ATA DA REUNIÃO" in first.title
    assert first.published_at is not None


def test_parse_strips_html_from_summary():
    content = load_text_fixture("cvm_feed_sample_decisoes.xml")
    items, _ = parse_entries("decisoes", content)
    for item in items:
        if item.summary:
            assert "<p>" not in item.summary
            assert "<" not in item.summary


def test_parse_malformed_feed_sets_bozo_but_still_extracts_valid_items():
    content = load_text_fixture("cvm_feed_sample_malformed.xml")
    items, bozo = parse_entries("decisoes", content)

    assert bozo is True
    # o primeiro item (bem formado) deve ser recuperado mesmo com o resto malformado
    assert len(items) >= 1
    assert items[0].title == "Item antes da quebra"
