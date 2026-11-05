from typing import Any, Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ai-goods-description"
    app_env: Literal["dev", "prod"] = "dev"
    debug: bool = True
    log_level: str = "INFO"

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2
    llm_timeout: float = 60.0
    llm_max_retries: int = 2
    llm_max_tokens: int = 4000
    # "json_schema" — strict structured output; "json_object" — for providers/models
    # without JSON schema support (the schema is then passed in the prompt)
    llm_response_format: Literal["json_schema", "json_object"] = "json_schema"
    # How many times to ask the model to fix a card that failed automatic checks
    llm_repair_attempts: int = 1
    # Provider-specific request params passed as is, JSON in env.
    # E.g. for reasoning models on OpenRouter: {"reasoning": {"effort": "low"}}
    llm_extra_body: dict[str, Any] = {}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
