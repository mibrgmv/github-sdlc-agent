from unittest.mock import MagicMock

import pytest

from src.agents.reviewer_agent import ReviewerAgent
from src.models import ReviewIssue, ReviewResponse


def make_agent() -> ReviewerAgent:
    agent = ReviewerAgent.__new__(ReviewerAgent)
    agent.settings = MagicMock()
    agent.github = MagicMock()
    agent.llm = MagicMock()
    return agent


# --- _extract_issue_number ---

def test_extract_issue_number_closes():
    assert make_agent()._extract_issue_number("Closes #42") == 42


def test_extract_issue_number_fixes():
    assert make_agent()._extract_issue_number("Fixes #7") == 7


def test_extract_issue_number_resolves():
    assert make_agent()._extract_issue_number("Resolves #100") == 100


def test_extract_issue_number_bare_hash():
    assert make_agent()._extract_issue_number("See issue #15 for context") == 15


def test_extract_issue_number_none():
    assert make_agent()._extract_issue_number("no issue reference here") is None


# --- _parse_response ---

def test_parse_response_valid():
    agent = make_agent()
    json_str = """{
        "summary": "LGTM",
        "issues": [],
        "meets_requirements": true
    }"""
    result = agent._parse_response(json_str)
    assert result is not None
    assert result.summary == "LGTM"
    assert result.approved is False  # default


def test_parse_response_with_issues():
    agent = make_agent()
    json_str = """{
        "summary": "Has issues",
        "issues": [{"severity": "error", "description": "NPE", "file": "src/app.py", "line": 10}],
        "meets_requirements": false
    }"""
    result = agent._parse_response(json_str)
    assert result is not None
    assert len(result.issues) == 1
    assert result.issues[0].severity == "error"


def test_parse_response_invalid_json():
    assert make_agent()._parse_response("not json at all") is None


def test_parse_response_json_wrapped_in_text():
    agent = make_agent()
    response = 'Here is my review:\n{"summary": "ok", "meets_requirements": true}\nDone.'
    result = agent._parse_response(response)
    assert result is not None
    assert result.summary == "ok"


def test_parse_response_invalid_schema():
    assert make_agent()._parse_response('{"summary": "ok"}') is None


def test_parse_response_invalid_severity():
    agent = make_agent()
    json_str = """{
        "summary": "Issues",
        "issues": [{"severity": "critical", "description": "Bad"}],
        "meets_requirements": false
    }"""
    assert agent._parse_response(json_str) is None


# --- _check_ci_status ---

def test_check_ci_status_passed():
    agent = make_agent()
    runs = [{"name": "tests", "conclusion": "success", "status": "completed"}]
    assert agent._check_ci_status(runs) == []


def test_check_ci_status_failed():
    agent = make_agent()
    runs = [{"name": "tests", "conclusion": "failure", "status": "completed"}]
    result = agent._check_ci_status(runs)
    assert len(result) == 1
    assert result[0]["severity"] == "error"
    assert result[0]["source"] == "ci"


def test_check_ci_status_empty():
    assert make_agent()._check_ci_status([]) == []


# --- _post_review ---

def test_post_review_approve():
    agent = make_agent()
    review = ReviewResponse(summary="All good", issues=[], meets_requirements=True)
    review.approved = True
    agent._post_review(1, review, 0, True)
    agent.github.create_pr_review.assert_called_once()
    _, kwargs = agent.github.create_pr_review.call_args
    assert kwargs["event"] == "APPROVE"


def test_post_review_request_changes():
    agent = make_agent()
    review = ReviewResponse(
        summary="Needs work",
        issues=[ReviewIssue(severity="error", description="Bug")],
        meets_requirements=False,
    )
    review.approved = False
    agent._post_review(1, review, 1, False)
    _, kwargs = agent.github.create_pr_review.call_args
    assert kwargs["event"] == "REQUEST_CHANGES"


def test_post_review_body_contains_summary():
    agent = make_agent()
    review = ReviewResponse(summary="Everything looks great", issues=[], meets_requirements=True)
    review.approved = True
    agent._post_review(5, review, 0, True)
    _, kwargs = agent.github.create_pr_review.call_args
    assert "Everything looks great" in kwargs["body"]


def test_post_review_body_has_blocking_section():
    agent = make_agent()
    review = ReviewResponse(
        summary="Problems",
        issues=[ReviewIssue(severity="requirement", description="Missing function", file="src/app.py")],
        meets_requirements=False,
    )
    review.approved = False
    agent._post_review(3, review, 2, True)
    _, kwargs = agent.github.create_pr_review.call_args
    assert "Blocking Issues" in kwargs["body"]
    assert "Missing function" in kwargs["body"]
    assert "Iteration 2" in kwargs["body"]


def test_post_review_body_has_suggestions_section():
    agent = make_agent()
    review = ReviewResponse(
        summary="Minor suggestions",
        issues=[ReviewIssue(severity="style", description="Rename variable")],
        meets_requirements=True,
    )
    review.approved = True
    agent._post_review(3, review, 0, True)
    _, kwargs = agent.github.create_pr_review.call_args
    assert "Suggestions" in kwargs["body"]
    assert "Rename variable" in kwargs["body"]
