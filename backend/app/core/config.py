from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    llm_provider: str = "groq"
    llm_api_key: str | None = None
    llm_model: str = "llama-3.1-8b-instant"
    log_level: str = "INFO"
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    # Fields are populated from environment variables at runtime by pydantic-settings;
    # mypy can't see that, hence the call-arg ignore.
    return Settings()  # type: ignore[call-arg]
