"""Configuração centralizada da aplicação."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Configurações carregadas do ambiente."""

    app_name: str = "n1-support-agents"
    environment: str = "development"
    log_level: str = "INFO"
    model_name: str = "claude-sonnet-5"
    model_base_url: str = (
        "https://litellm.tech4humans.com.br/v1/chat/completions"
    )
    mcp_endpoint: str = "http://localhost:8765/mcp"
    agent_name: str = "orquestrador"
    mcp_timeout_seconds: float = 15.0
    openai_api_key: str | None = None


def get_settings() -> Settings:
    """Retorna configurações sem expor valores sensíveis em logs."""

    load_dotenv()
    return Settings(
        app_name=os.getenv("APP_NAME", Settings.app_name),
        environment=os.getenv("ENVIRONMENT", Settings.environment),
        log_level=os.getenv("LOG_LEVEL", Settings.log_level),
        model_name=os.getenv("MODEL_NAME", Settings.model_name),
        model_base_url=os.getenv("MODEL_BASE_URL", Settings.model_base_url),
        mcp_endpoint=os.getenv("MCP_ENDPOINT", Settings.mcp_endpoint),
        agent_name=Settings.agent_name,
        mcp_timeout_seconds=float(
            os.getenv("MCP_TIMEOUT_SECONDS", Settings.mcp_timeout_seconds)
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )
