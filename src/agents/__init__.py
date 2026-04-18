from src.agents.base import Agent
from src.agents.code_agent import CodeAgent
from src.agents.pr_desc_agent import PRDescAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.agents.test_gen_agent import TestGenAgent

REGISTRY: dict[str, type[Agent]] = {
    "code": CodeAgent,
    "reviewer": ReviewerAgent,
    "pr_desc": PRDescAgent,
    "test_gen": TestGenAgent,
}

__all__ = ["Agent", "CodeAgent", "ReviewerAgent", "PRDescAgent", "TestGenAgent", "REGISTRY"]
