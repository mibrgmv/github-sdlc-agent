from typing import Literal

from pydantic import BaseModel

BLOCKING_SEVERITIES = {"error", "requirement"}
NON_BLOCKING_SEVERITIES = {"refactor", "style", "suggestion"}


class ReviewIssue(BaseModel):
    severity: Literal["error", "requirement", "refactor", "style", "suggestion"]
    description: str
    file: str | None = None
    line: int | None = None
    source: str | None = None  # "ci" for CI-generated issues


class ReviewResponse(BaseModel):
    summary: str
    issues: list[ReviewIssue] = []
    meets_requirements: bool
    approved: bool = False  # computed after parsing, not from LLM


class FileChange(BaseModel):
    path: str
    action: Literal["create", "modify", "delete"]
    content: str = ""


class CodeChangesResponse(BaseModel):
    analysis: str
    changes: list[FileChange]
    commit_message: str
    pr_title: str
    pr_body: str
