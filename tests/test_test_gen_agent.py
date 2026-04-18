from unittest.mock import MagicMock, patch

from src.agents.test_gen_agent import SKIP_COMMIT_TAG, TestGenAgent
from src.models import TestGenResponse


def make_agent() -> TestGenAgent:
    agent = TestGenAgent.__new__(TestGenAgent)
    agent.settings = MagicMock()
    agent.github = MagicMock()
    agent.llm = MagicMock()
    return agent


# --- _parse_response ---

def test_parse_response_valid():
    agent = make_agent()
    json_str = """{
        "analysis": "need tests for foo",
        "tests": [{"path": "tests/test_foo.py", "content": "def test_x(): pass"}],
        "commit_message": "add tests"
    }"""
    result = agent._parse_response(json_str)
    assert isinstance(result, TestGenResponse)
    assert len(result.tests) == 1


def test_parse_response_empty_tests_is_valid():
    agent = make_agent()
    json_str = '{"analysis": "nothing meaningful to test", "tests": [], "commit_message": "n/a"}'
    result = agent._parse_response(json_str)
    assert result is not None
    assert result.tests == []


def test_parse_response_invalid_json():
    assert make_agent()._parse_response("not json") is None


def test_parse_response_missing_fields():
    assert make_agent()._parse_response('{"analysis": "x"}') is None


# --- run: skip conditions ---

def test_run_skips_when_no_source_files():
    agent = make_agent()
    agent.github.get_pull_request.return_value = MagicMock()
    agent.github.get_pr_files.return_value = [
        {"filename": "README.md", "status": "modified"},
        {"filename": "tests/test_x.py", "status": "modified"},
    ]

    result = agent.run(pr_number=1)
    assert result["success"] is True
    assert result["skipped"] is True
    agent.llm.chat.assert_not_called()


def test_run_skips_removed_files():
    agent = make_agent()
    agent.github.get_pull_request.return_value = MagicMock()
    agent.github.get_pr_files.return_value = [
        {"filename": "src/old.py", "status": "removed"},
    ]

    result = agent.run(pr_number=1)
    assert result["success"] is True
    assert result["skipped"] is True


def test_run_skips_when_llm_returns_empty_tests():
    agent = make_agent()
    pr = MagicMock()
    pr.title = "add feature"
    pr.head.ref = "feature-branch"
    agent.github.get_pull_request.return_value = pr
    agent.github.get_pr_files.return_value = [{"filename": "src/foo.py", "status": "added"}]
    agent.github.get_pr_diff.return_value = "diff"
    agent.github.get_file_content.return_value = "def foo(): pass"
    agent.llm.chat.return_value = '{"analysis": "trivial", "tests": [], "commit_message": "n/a"}'

    result = agent.run(pr_number=1)
    assert result["success"] is True
    assert result["skipped"] is True
    assert "trivial" in result["reason"]


def test_run_parse_failure_returns_error():
    agent = make_agent()
    pr = MagicMock()
    pr.title = "x"
    pr.head.ref = "b"
    agent.github.get_pull_request.return_value = pr
    agent.github.get_pr_files.return_value = [{"filename": "src/foo.py", "status": "added"}]
    agent.github.get_pr_diff.return_value = "diff"
    agent.github.get_file_content.return_value = "code"
    agent.llm.chat.return_value = "garbage"

    result = agent.run(pr_number=1)
    assert result["success"] is False


@patch("src.agents.test_gen_agent.Repo")
@patch("src.agents.test_gen_agent.tempfile.TemporaryDirectory")
def test_run_commits_and_pushes_tests(mock_tmpdir, mock_repo_cls, tmp_path):
    mock_tmpdir.return_value.__enter__.return_value = str(tmp_path)

    mock_repo = MagicMock()
    mock_repo.index.diff.return_value = ["some diff"]
    mock_commit = MagicMock()
    mock_commit.hexsha = "abcdef1234"
    mock_repo.index.commit.return_value = mock_commit
    mock_repo_cls.clone_from.return_value = mock_repo

    agent = make_agent()
    agent.github.get_installation_token.return_value = "token"
    agent.github.repo.full_name = "owner/repo"
    pr = MagicMock()
    pr.title = "add"
    pr.head.ref = "feat"
    agent.github.get_pull_request.return_value = pr
    agent.github.get_pr_files.return_value = [{"filename": "src/foo.py", "status": "added"}]
    agent.github.get_pr_diff.return_value = "diff"
    agent.github.get_file_content.return_value = "def foo(): pass"
    agent.llm.chat.return_value = (
        '{"analysis": "adds foo", '
        '"tests": [{"path": "tests/test_foo.py", "content": "def test_foo(): pass"}], '
        '"commit_message": "add tests"}'
    )

    result = agent.run(pr_number=1)

    assert result["success"] is True
    assert result["tests_added"] == 1
    assert result["commit"] == "abcdef1"
    commit_msg = mock_repo.index.commit.call_args[0][0]
    assert SKIP_COMMIT_TAG in commit_msg
    mock_repo.remote.return_value.push.assert_called_once()
