import pytest
from pydantic import ValidationError

from src.models import CodeChangesResponse, FileChange, ReviewIssue, ReviewResponse


def test_review_response_valid():
    data = {
        "approved": True,
        "summary": "Looks good",
        "issues": [],
        "meets_requirements": True,
        "requirements_feedback": "All good",
    }
    review = ReviewResponse.model_validate(data)
    assert review.approved is True
    assert review.summary == "Looks good"
    assert review.issues == []


def test_review_response_defaults():
    review = ReviewResponse(approved=False, summary="Needs work", meets_requirements=False)
    assert review.issues == []
    assert review.requirements_feedback == ""


def test_review_response_invalid_severity():
    data = {
        "approved": False,
        "summary": "Issues found",
        "issues": [{"severity": "blocker", "description": "Something bad"}],
        "meets_requirements": False,
    }
    with pytest.raises(ValidationError):
        ReviewResponse.model_validate(data)


def test_review_response_missing_required():
    with pytest.raises(ValidationError):
        ReviewResponse.model_validate({"approved": True})


def test_review_issue_optional_fields():
    issue = ReviewIssue(severity="minor", description="Style nit")
    assert issue.file is None
    assert issue.line is None


def test_review_issue_with_location():
    issue = ReviewIssue(severity="critical", description="Null pointer", file="src/app.py", line=42)
    assert issue.file == "src/app.py"
    assert issue.line == 42


def test_code_changes_response_valid():
    data = {
        "analysis": "Need to add function",
        "changes": [{"path": "src/foo.py", "action": "create", "content": "def foo(): pass"}],
        "commit_message": "Add foo",
        "pr_title": "Add foo feature",
        "pr_body": "Closes #1",
    }
    result = CodeChangesResponse.model_validate(data)
    assert len(result.changes) == 1
    assert result.changes[0].action == "create"
    assert result.changes[0].path == "src/foo.py"


def test_code_changes_response_invalid_action():
    data = {
        "analysis": "...",
        "changes": [{"path": "foo.py", "action": "overwrite", "content": ""}],
        "commit_message": "msg",
        "pr_title": "title",
        "pr_body": "body",
    }
    with pytest.raises(ValidationError):
        CodeChangesResponse.model_validate(data)


def test_file_change_delete_no_content():
    change = FileChange(path="foo.py", action="delete")
    assert change.content == ""


def test_file_change_all_actions():
    for action in ("create", "modify", "delete"):
        change = FileChange(path="f.py", action=action)
        assert change.action == action
