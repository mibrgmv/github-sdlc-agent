from unittest.mock import MagicMock

import pytest

from src.agents.code_agent import CodeAgent
from src.models import CodeChangesResponse


def make_agent() -> CodeAgent:
    agent = CodeAgent.__new__(CodeAgent)
    agent.settings = MagicMock()
    agent.github = MagicMock()
    agent.llm = MagicMock()
    return agent


# --- _parse_response ---

def test_parse_response_valid():
    agent = make_agent()
    json_str = """{
        "analysis": "Need to add feature",
        "changes": [{"path": "src/foo.py", "action": "create", "content": "def foo(): pass"}],
        "commit_message": "Add foo",
        "pr_title": "Add foo",
        "pr_body": "Closes #1"
    }"""
    result = agent._parse_response(json_str)
    assert result is not None
    assert isinstance(result, CodeChangesResponse)
    assert len(result.changes) == 1
    assert result.changes[0].action == "create"


def test_parse_response_multiple_changes():
    agent = make_agent()
    json_str = """{
        "analysis": "Refactor",
        "changes": [
            {"path": "src/a.py", "action": "modify", "content": "x = 1"},
            {"path": "src/b.py", "action": "delete"}
        ],
        "commit_message": "Refactor a and b",
        "pr_title": "Refactor",
        "pr_body": "Closes #2"
    }"""
    result = agent._parse_response(json_str)
    assert result is not None
    assert len(result.changes) == 2
    assert result.changes[1].action == "delete"


def test_parse_response_invalid_json():
    assert make_agent()._parse_response("not json") is None


def test_parse_response_missing_changes():
    agent = make_agent()
    result = agent._parse_response(
        '{"analysis": "ok", "commit_message": "msg", "pr_title": "t", "pr_body": "b"}'
    )
    assert result is None


def test_parse_response_invalid_action():
    agent = make_agent()
    json_str = """{
        "analysis": "...",
        "changes": [{"path": "foo.py", "action": "overwrite", "content": ""}],
        "commit_message": "msg",
        "pr_title": "title",
        "pr_body": "body"
    }"""
    assert agent._parse_response(json_str) is None


def test_parse_response_json_in_text():
    agent = make_agent()
    wrapped = 'Sure! Here are the changes:\n{"analysis": "x", "changes": [{"path": "f.py", "action": "create", "content": ""}], "commit_message": "c", "pr_title": "t", "pr_body": "b"}'
    result = agent._parse_response(wrapped)
    assert result is not None


# --- _get_relevant_files ---

def test_get_relevant_files_keyword_match():
    agent = make_agent()
    files = ["src/auth.py", "src/server.py", "README.md", "config.yml"]
    result = agent._get_relevant_files("fix auth bug", "authentication issue", files)
    assert "src/auth.py" in result


def test_get_relevant_files_includes_code_files():
    agent = make_agent()
    files = ["src/unrelated.py", "data/dump.sql", "notes.txt"]
    result = agent._get_relevant_files("some task", "description", files)
    assert "src/unrelated.py" in result
    assert "data/dump.sql" not in result


def test_get_relevant_files_limit():
    agent = make_agent()
    files = [f"src/file{i}.py" for i in range(50)]
    result = agent._get_relevant_files("something", "description", files)
    assert len(result) <= 20


def test_get_relevant_files_empty():
    agent = make_agent()
    result = agent._get_relevant_files("task", "desc", [])
    assert result == []
