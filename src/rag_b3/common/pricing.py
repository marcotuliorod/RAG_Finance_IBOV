"""Tabela de preço por modelo Anthropic, para estimar custo a partir de
tokens reais (nunca inventados) reportados pela API em `response.usage`.

Preços em USD por 1M de tokens, capturados em 2026-08-27 (ver
docs/evaluation/methodology.md para a fonte). Reconferir na página oficial
de pricing da Anthropic antes de usar estes números para decisão de
orçamento real — preços mudam sem aviso prévio no código."""

from dataclasses import dataclass

CAPTURED_AT = "2026-08-27"


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: float
    output_per_million: float


PRICING: dict[str, ModelPrice] = {
    "claude-sonnet-5": ModelPrice(input_per_million=2.00, output_per_million=10.00),
    "claude-opus-4-8": ModelPrice(input_per_million=5.00, output_per_million=25.00),
}


def estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float | None:
    """Retorna None (em vez de um número inventado) se o modelo não estiver
    na tabela — nunca extrapola preço de um modelo desconhecido."""
    price = PRICING.get(model_id)
    if price is None:
        return None
    return (
        input_tokens / 1_000_000 * price.input_per_million
        + output_tokens / 1_000_000 * price.output_per_million
    )
