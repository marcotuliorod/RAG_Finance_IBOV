from rag_b3.common.pricing import estimate_cost_usd


def test_estimate_cost_usd_known_model():
    cost = estimate_cost_usd("claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 12.00  # $2 input + $10 output por 1M tokens


def test_estimate_cost_usd_unknown_model_returns_none_instead_of_guessing():
    assert estimate_cost_usd("some-future-model", input_tokens=1000, output_tokens=1000) is None


def test_estimate_cost_usd_zero_tokens_is_zero_cost():
    assert estimate_cost_usd("claude-opus-4-8", input_tokens=0, output_tokens=0) == 0.0
