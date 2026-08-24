class BrapiError(Exception):
    """Base para todos os erros do cliente brapi.dev."""

    def __init__(self, code: str, message: str, raw: dict | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.raw = raw


class BrapiAuthError(BrapiError):
    """HTTP 401/403 — token ausente ou inválido. Fatal, aborta o job
    inteiro (diferente da HG Brasil, aqui é 1 única requisição em lote para
    toda a watchlist, então não há "pular só um ticker")."""


class BrapiPossibleQuotaExceeded(BrapiError):
    """HTTP 429 — limite de requisições do plano atingido."""


class BrapiRequestError(BrapiError):
    """Demais erros da API (400/404, ou corpo 200 com campo "error")."""
