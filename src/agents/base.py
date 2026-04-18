from abc import ABC, abstractmethod

from src.config import Settings
from src.github_client import GitHubClient
from src.llm_client import LLMClient


class Agent(ABC):
    def __init__(self, settings: Settings, repo: str):
        self.settings = settings
        self.github = GitHubClient(settings, repo)
        self.llm = LLMClient(settings)

    @abstractmethod
    def run(self, *args, **kwargs) -> dict:
        ...
