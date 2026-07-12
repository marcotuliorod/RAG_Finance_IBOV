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

    supabase_db_url: str = Field(alias="SUPABASE_DB_URL")

    watchlist_path: Path = Path("config/watchlist.yaml")
    timezone: str = "America/Sao_Paulo"


def get_settings() -> Settings:
    return Settings()
