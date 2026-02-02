import os
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_private_key_path: str = ""
    github_app_installation_id: str = ""
    github_webhook_secret: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    max_iterations: int = 5

    class Config:
        env_file = ".env"
        extra = "ignore"

    @model_validator(mode="after")
    def load_private_key_from_file(self):
        if not self.github_app_private_key and self.github_app_private_key_path:
            if os.path.exists(self.github_app_private_key_path):
                with open(self.github_app_private_key_path) as f:
                    self.github_app_private_key = f.read()
        return self


def get_settings() -> Settings:
    return Settings()
