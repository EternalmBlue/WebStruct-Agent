from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WebStruct-Agent"
    environment: str = "local"
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DEEPSEEK_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"),
    )
    llm_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias=AliasChoices("DEEPSEEK_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    llm_model: str = Field(
        default="deepseek-chat",
        validation_alias=AliasChoices("DEEPSEEK_MODEL", "LLM_MODEL", "OPENAI_MODEL"),
    )
    llm_timeout_seconds: float = Field(default=30.0, validation_alias="LLM_TIMEOUT_SECONDS")
    database_url: str = Field(
        default="postgresql+psycopg://webstruct:webstruct@127.0.0.1:5432/webstruct_agent",
        validation_alias="DATABASE_URL",
    )
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def model_mode(self) -> str:
        return "deepseek" if "deepseek" in self.llm_base_url else "openai-compatible"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def database_driver(self) -> str:
        return self.database_url.split(":", maxsplit=1)[0]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
