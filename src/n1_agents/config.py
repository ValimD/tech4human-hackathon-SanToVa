"""Configuração centralizada da aplicação."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Configurações carregadas do ambiente."""

    app_name: str = "n1-support-agents"
    environment: str = "development"
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Retorna configurações sem expor valores sensíveis em logs."""

    return Settings(
        app_name=os.getenv("APP_NAME", Settings.app_name),
        environment=os.getenv("ENVIRONMENT", Settings.environment),
        log_level=os.getenv("LOG_LEVEL", Settings.log_level),
    )
