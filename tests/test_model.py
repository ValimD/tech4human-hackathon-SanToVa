import pytest

from n1_agents.config import get_settings
from n1_agents.model import create_chat_model


def test_settings_use_hackathon_model_by_default(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-5")
    monkeypatch.setenv(
        "MODEL_BASE_URL",
        "https://litellm.tech4humans.com.br/v1/chat/completions",
    )

    settings = get_settings()

    assert settings.model_name == "claude-sonnet-5"
    assert settings.model_base_url == (
        "https://litellm.tech4humans.com.br/v1/chat/completions"
    )
    assert settings.agent_name == "orquestrador"


def test_model_factory_uses_configured_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-5")

    model = create_chat_model(get_settings())

    assert model.model_name == "claude-sonnet-5"
    assert model.max_tokens == 16000
    assert model.max_retries == 2
    assert model.openai_api_key.get_secret_value() == "test-key"
    assert model.openai_api_base == "https://litellm.tech4humans.com.br/v1"


def test_model_factory_rejects_missing_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_chat_model(get_settings())
