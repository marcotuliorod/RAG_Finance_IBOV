import anthropic

from rag_b3.config.settings import get_settings


def get_anthropic_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def get_model() -> str:
    return get_settings().anthropic_model
