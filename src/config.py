import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_token: str = ""
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_installation_id: str = ""
    github_webhook_secret: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    max_iterations: int = 5
    target_repo: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

    def use_github_app(self) -> bool:
        return bool(self.github_app_id and self.github_app_private_key)


def get_settings() -> Settings:
    private_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
    private_key_path = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "")
    if private_key_path and os.path.exists(private_key_path):
        with open(private_key_path) as f:
            private_key = f.read()

    return Settings(
        github_token=os.getenv("GITHUB_TOKEN", ""),
        github_app_id=os.getenv("GITHUB_APP_ID", ""),
        github_app_private_key=private_key,
        github_app_installation_id=os.getenv("GITHUB_APP_INSTALLATION_ID", ""),
        github_webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "5")),
        target_repo=os.getenv("TARGET_REPO", ""),
    )
