"""환경설정: .env(저장소 루트) + 환경변수 → Config."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).parents[2]


class Config(BaseSettings):
    database_url: str = "postgresql://insight:insight@localhost:5434/insight"
    database_url_test: str = "postgresql://insight:insight@localhost:5434/insight_test"
    github_token: str | None = None
    admin_token: str = "change-me"
    llm_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "meta/llama-3.3-70b-instruct"

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_config() -> Config:
    return Config()
