class HgBrasilError(Exception):
    """Base para todos os erros do cliente HG Brasil."""

    def __init__(self, code: str, message: str, raw: dict | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.raw = raw


class HgBrasilAuthError(HgBrasilError):
    """INVALID_API_KEY / UNAUTHORIZED_KEY — fatal, aborta o job inteiro."""


class HgBrasilTickerError(HgBrasilError):
    """REQUIRED_TICKER / INVALID_TICKER — não fatal, pula só este ticker."""


class HgBrasilRequestError(HgBrasilError):
    """Demais códigos documentados (datas/ranges) — não fatal, não esperado no uso V1."""


class HgBrasilUnknownError(HgBrasilError):
    """Código de erro fora do catálogo documentado — não fatal, mas logar raw completo."""


class HgBrasilPossibleQuotaExceeded(HgBrasilError):
    """Sinal fora do catálogo que parece indicar limite de cota (429 ou texto
    'limit'/'quota') — não documentado pela HG Brasil. Tratar com circuit
    breaker: aborta o job imediatamente para revisão humana."""


class HgBrasilPlanRestrictedError(HgBrasilError):
    """results.error=true + message pedindo plano superior — formato
    diferente do catálogo de `errors[]` documentado (confirmado ao vivo em
    2026-07-11: /finance/stock_price responde HTTP 200 com
    {"results": {"error": true, "message": "Esta consulta necessita do
    plano Member Premium ou superior."}} para QUALQUER símbolo no plano
    free). Como é uma restrição de plano (não de ticker específico), tratar
    como fatal para a fase de cotações por ticker — insistir em outros
    tickers só desperdiça cota, já que todos falhariam do mesmo jeito."""


# Mapeamento dos códigos documentados publicamente (ver PRD/plan) para as
# exceções acima. Qualquer código fora deste dict vira HgBrasilUnknownError.
_AUTH_CODES = {"INVALID_API_KEY", "UNAUTHORIZED_KEY"}
_TICKER_CODES = {"REQUIRED_TICKER", "INVALID_TICKER"}
_REQUEST_CODES = {
    "INVALID_TIME_SERIES",
    "MAX_PER_REQUEST",
    "INVALID_RANGE",
    "HISTORICAL_DATE_LIMIT",
    "INVALID_DATE",
    "INVALID_DATE_RANGE",
    "INVALID_PARAMETER",
    "REQUIRED_DATE",
}


def error_from_code(code: str, message: str, raw: dict | None = None) -> HgBrasilError:
    if code in _AUTH_CODES:
        return HgBrasilAuthError(code, message, raw)
    if code in _TICKER_CODES:
        return HgBrasilTickerError(code, message, raw)
    if code in _REQUEST_CODES:
        return HgBrasilRequestError(code, message, raw)
    return HgBrasilUnknownError(code, message, raw)
