from typing import Literal

from pydantic import BaseModel


class ReviewIssue(BaseModel):
    severity: Literal["critical", "major", "minor", "suggestion"]
    description: str
    file: str | None = None
    line: int | None = None


class ReviewResponse(BaseModel):
    approved: bool
    summary: str
    issues: list[ReviewIssue] = []
    meets_requirements: bool
    requirements_feedback: str = ""


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
