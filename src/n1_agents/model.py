"""Fábrica do modelo de linguagem usado pelos agentes."""

from langchain_openai import ChatOpenAI

from .config import Settings, get_settings


def _client_base_url(endpoint: str) -> str:
    """Converte o endpoint de chat no base URL esperado pelo SDK OpenAI."""

    return endpoint.removesuffix("/chat/completions").rstrip("/")


def create_chat_model(settings: Settings | None = None) -> ChatOpenAI:
    """Cria o modelo configurado sem realizar uma chamada à API."""

    resolved_settings = settings or get_settings()
    if not resolved_settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY não configurada. Defina-a no arquivo .env ou no ambiente."
        )

    return ChatOpenAI(
        model=resolved_settings.model_name,
        api_key=resolved_settings.openai_api_key,
        base_url=_client_base_url(resolved_settings.model_base_url),
        max_tokens=16000,
        max_retries=2,
        temperature=0,
    )
