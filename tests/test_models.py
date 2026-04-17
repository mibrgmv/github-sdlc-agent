import pytest
from pydantic import ValidationError

from src.models import CodeChangesResponse, FileChange, ReviewIssue, ReviewResponse


def test_review_response_valid():
    data = {
        "summary": "Looks good",
        "issues": [],
        "meets_requirements": True,
    }
    review = ReviewResponse.model_validate(data)
    assert review.summary == "Looks good"
    assert review.issues == []
    assert review.approved is False  # default, computed later


def test_review_response_approved_default_false():
    review = ReviewResponse(summary="ok", meets_requirements=True)
    assert review.approved is False


def test_review_response_approved_settable():
    review = ReviewResponse(summary="ok", meets_requirements=True)
    review.approved = True
    assert review.approved is True


def test_review_response_missing_required():
    with pytest.raises(ValidationError):
        ReviewResponse.model_validate({"summary": "ok"})


def test_review_issue_valid_severities():
    for severity in ("error", "requirement", "refactor", "style", "suggestion"):
        issue = ReviewIssue(severity=severity, description="test")
        assert issue.severity == severity


def test_review_issue_invalid_severity():
    with pytest.raises(ValidationError):
        ReviewIssue(severity="critical", description="test")


def test_review_issue_optional_fields():
    issue = ReviewIssue(severity="error", description="Bug")
    assert issue.file is None
    assert issue.line is None
    assert issue.source is None


def test_review_issue_with_location():
    issue = ReviewIssue(severity="error", description="NPE", file="src/app.py", line=42, source="ci")
    assert issue.file == "src/app.py"
    assert issue.line == 42
    assert issue.source == "ci"


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
