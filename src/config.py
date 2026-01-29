import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_token: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    max_iterations: int = 5
    target_repo: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


def get_settings() -> Settings:
    return Settings(
        github_token=os.getenv("GITHUB_TOKEN", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "5")),
        target_repo=os.getenv("TARGET_REPO", ""),
    )
