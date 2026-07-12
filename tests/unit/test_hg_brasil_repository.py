from rag_b3.ingestion.hg_brasil.repository import (
    _extract_asset_dict,
    _extract_snapshot_fields,
    _extract_taxes,
)
from tests.conftest import load_json_fixture


def test_extract_snapshot_fields_from_real_shape_fixture():
    # Formato real observado na API (taxes é LISTA, não dict) — ver
    # repository.py:_extract_taxes. Confirmado contra a API ao vivo em
    # 2026-07-11.
    fixture = load_json_fixture("hg_brasil_finance_ok.json")
    fields = _extract_snapshot_fields(fixture)

    assert fields["ibovespa_points"] == 132456.78
    assert fields["ifix_points"] == 3210.5
    assert fields["usd_brl"] == 5.32
    assert fields["cdi_rate"] == 14.25
    assert fields["selic_rate"] == 14.25


def test_extract_taxes_handles_list_shape():
    taxes = [{"date": "2026-07-13", "cdi": 14.25, "selic": 14.25}]
    cdi, selic = _extract_taxes(taxes)
    assert cdi == 14.25
    assert selic == 14.25


def test_extract_taxes_handles_legacy_dict_shape_as_fallback():
    taxes = {"CDI": {"value": 10.9}, "SELIC": {"value": 11.0}}
    cdi, selic = _extract_taxes(taxes)
    assert cdi == 10.9
    assert selic == 11.0


def test_extract_taxes_handles_missing_or_malformed_data():
    assert _extract_taxes(None) == (None, None)
    assert _extract_taxes([]) == (None, None)
    assert _extract_taxes({}) == (None, None)
    assert _extract_taxes("unexpected string") == (None, None)


def test_extract_snapshot_fields_never_raises_on_missing_sections():
    # raw_response sempre é persistido por completo mesmo se a extração
    # tipada falhar — a função nunca deve lançar exceção.
    fields = _extract_snapshot_fields({"results": {}})
    assert fields == {
        "ibovespa_points": None,
        "ifix_points": None,
        "usd_brl": None,
        "cdi_rate": None,
        "selic_rate": None,
    }
    assert _extract_snapshot_fields({}) == fields


def test_extract_asset_dict_from_real_shape_fixture():
    fixture = load_json_fixture("hg_brasil_stock_price_ok.json")
    asset = _extract_asset_dict(fixture, "PETR4")
    assert asset is not None
    assert asset["price"] == 38.42
