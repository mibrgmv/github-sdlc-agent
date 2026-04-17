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
        "approved": true,
        "summary": "LGTM",
        "issues": [],
        "meets_requirements": true,
        "requirements_feedback": "All good"
    }"""
    result = agent._parse_response(json_str)
    assert result is not None
    assert result.approved is True
    assert result.summary == "LGTM"


def test_parse_response_with_issues():
    agent = make_agent()
    json_str = """{
        "approved": false,
        "summary": "Has issues",
        "issues": [{"severity": "major", "description": "Bug", "file": "src/app.py", "line": 10}],
        "meets_requirements": false
    }"""
    result = agent._parse_response(json_str)
    assert result is not None
    assert len(result.issues) == 1
    assert result.issues[0].severity == "major"


def test_parse_response_invalid_json():
    assert make_agent()._parse_response("not json at all") is None


def test_parse_response_json_wrapped_in_text():
    agent = make_agent()
    response = 'Here is my review:\n{"approved": true, "summary": "ok", "meets_requirements": true}\nDone.'
    result = agent._parse_response(response)
    assert result is not None
    assert result.approved is True


def test_parse_response_invalid_schema():
    assert make_agent()._parse_response('{"approved": true}') is None


def test_parse_response_invalid_severity():
    agent = make_agent()
    json_str = """{
        "approved": false,
        "summary": "Issues",
        "issues": [{"severity": "blocker", "description": "Bad"}],
        "meets_requirements": false
    }"""
    assert agent._parse_response(json_str) is None


# --- _post_review ---

def test_post_review_approve():
    agent = make_agent()
    review = ReviewResponse(
        approved=True, summary="All good", issues=[], meets_requirements=True
    )
    agent._post_review(1, review)
    agent.github.create_pr_review.assert_called_once()
    _, kwargs = agent.github.create_pr_review.call_args
    assert kwargs["event"] == "APPROVE"


def test_post_review_request_changes():
    agent = make_agent()
    review = ReviewResponse(
        approved=False,
        summary="Needs work",
        issues=[ReviewIssue(severity="major", description="Bug found")],
        meets_requirements=False,
    )
    agent._post_review(1, review)
    _, kwargs = agent.github.create_pr_review.call_args
    assert kwargs["event"] == "REQUEST_CHANGES"


def test_post_review_body_contains_summary():
    agent = make_agent()
    review = ReviewResponse(
        approved=True, summary="Everything looks great", issues=[], meets_requirements=True
    )
    agent._post_review(5, review)
    _, kwargs = agent.github.create_pr_review.call_args
    assert "Everything looks great" in kwargs["body"]


def test_post_review_body_contains_issues():
    agent = make_agent()
    review = ReviewResponse(
        approved=False,
        summary="Problems found",
        issues=[ReviewIssue(severity="critical", description="Memory leak", file="src/server.py", line=42)],
        meets_requirements=False,
    )
    agent._post_review(3, review)
    _, kwargs = agent.github.create_pr_review.call_args
    assert "Memory leak" in kwargs["body"]
    assert "src/server.py" in kwargs["body"]
