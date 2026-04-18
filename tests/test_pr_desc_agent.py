from unittest.mock import MagicMock

from src.agents.pr_desc_agent import AUTO_MARKER, PRDescAgent
from src.models import PRDescriptionResponse


def make_agent() -> PRDescAgent:
    agent = PRDescAgent.__new__(PRDescAgent)
    agent.settings = MagicMock()
    agent.github = MagicMock()
    agent.llm = MagicMock()
    return agent


# --- _parse_response ---

def test_parse_response_valid():
    agent = make_agent()
    json_str = '{"summary": "Add feature", "body": "## Summary\\nDoes X"}'
    result = agent._parse_response(json_str)
    assert isinstance(result, PRDescriptionResponse)
    assert result.summary == "Add feature"


def test_parse_response_wrapped_in_text():
    agent = make_agent()
    wrapped = 'Sure!\n{"summary": "s", "body": "b"}\nDone.'
    result = agent._parse_response(wrapped)
    assert result is not None
    assert result.body == "b"


def test_parse_response_invalid_json():
    assert make_agent()._parse_response("not json") is None


def test_parse_response_missing_fields():
    assert make_agent()._parse_response('{"summary": "only"}') is None


# --- run: skip conditions ---

def test_run_skips_when_body_already_present():
    agent = make_agent()
    pr = MagicMock()
    pr.body = "This PR implements the feature described in the linked issue."
    agent.github.get_pull_request.return_value = pr

    result = agent.run(pr_number=1)
    assert result["success"] is True
    assert result["skipped"] is True
    agent.llm.chat.assert_not_called()


def test_run_regenerates_if_force():
    agent = make_agent()
    pr = MagicMock()
    pr.body = "Long existing body that would normally be skipped"
    pr.title = "Fix bug"
    agent.github.get_pull_request.return_value = pr
    agent.github.get_pr_diff.return_value = "diff"
    agent.github.get_pr_files.return_value = [{"filename": "a.py", "status": "modified"}]
    agent.llm.chat.return_value = '{"summary": "s", "body": "new body"}'

    result = agent.run(pr_number=1, force=True)
    assert result["success"] is True
    assert not result.get("skipped")
    agent.github.update_pull_request.assert_called_once()


def test_run_regenerates_if_marker_present():
    agent = make_agent()
    pr = MagicMock()
    pr.body = f"Previously-generated long body text for this PR {AUTO_MARKER}"
    pr.title = "Fix bug"
    agent.github.get_pull_request.return_value = pr
    agent.github.get_pr_diff.return_value = "diff"
    agent.github.get_pr_files.return_value = [{"filename": "a.py", "status": "modified"}]
    agent.llm.chat.return_value = '{"summary": "s", "body": "new body"}'

    result = agent.run(pr_number=1)
    assert result["success"] is True
    assert not result.get("skipped")


def test_run_short_body_triggers_generation():
    agent = make_agent()
    pr = MagicMock()
    pr.body = "wip"
    pr.title = "Fix bug"
    agent.github.get_pull_request.return_value = pr
    agent.github.get_pr_diff.return_value = "diff"
    agent.github.get_pr_files.return_value = [{"filename": "a.py", "status": "modified"}]
    agent.llm.chat.return_value = '{"summary": "s", "body": "generated body"}'

    result = agent.run(pr_number=1)
    assert result["success"] is True
    agent.github.update_pull_request.assert_called_once()
    _, kwargs = agent.github.update_pull_request.call_args
    assert AUTO_MARKER in kwargs["body"]
    assert "generated body" in kwargs["body"]


def test_run_returns_error_on_parse_fail():
    agent = make_agent()
    pr = MagicMock()
    pr.body = ""
    pr.title = "t"
    agent.github.get_pull_request.return_value = pr
    agent.github.get_pr_diff.return_value = "diff"
    agent.github.get_pr_files.return_value = []
    agent.llm.chat.return_value = "not json"

    result = agent.run(pr_number=1)
    assert result["success"] is False
    agent.github.update_pull_request.assert_not_called()
