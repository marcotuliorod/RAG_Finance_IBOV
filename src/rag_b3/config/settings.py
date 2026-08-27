from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_MODEL")

    hg_brasil_api_key: str = Field(alias="HG_BRASIL_API_KEY")
    hg_brasil_on_insufficient_budget: str = Field(
        default="partial", alias="HG_BRASIL_ON_INSUFFICIENT_BUDGET"
    )
    hg_brasil_safety_margin: float = Field(default=0.90, alias="HG_BRASIL_SAFETY_MARGIN")
    # Loop de cotação por ticker da HG Brasil (/finance/stock_price) fica
    # desligado por padrão: bloqueado no plano free (ver
    # ingestion/hg_brasil/errors.py:HgBrasilPlanRestrictedError) e
    # substituído pelo job brapi.dev (ingestion/brapi/). Mantido no código,
    # não removido, como fallback caso o plano HG Brasil mude no futuro.
    hg_brasil_stock_price_enabled: bool = Field(
        default=False, alias="HG_BRASIL_STOCK_PRICE_ENABLED"
    )

    # Token brapi.dev — opcional: PETR4/VALE3/ITUB4/MGLU3 respondem sem
    # token; os demais tickers da watchlist exigem um token do plano free.
    brapi_token: str | None = Field(default=None, alias="BRAPI_TOKEN")

    database_url: str = Field(alias="DATABASE_URL")

    watchlist_path: Path = Path("config/watchlist.yaml")
    timezone: str = "America/Sao_Paulo"


def get_settings() -> Settings:
    return Settings()
