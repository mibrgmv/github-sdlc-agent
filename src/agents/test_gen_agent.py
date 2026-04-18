import json
import logging
import tempfile
from pathlib import Path

from git import Repo
from pydantic import ValidationError

from src.agents.base import Agent
from src.models import TestGenResponse

logger = logging.getLogger(__name__)

SKIP_COMMIT_TAG = "[skip-agents]"

SYSTEM_PROMPT = """You are a test-writing assistant.

Given a diff of a Pull Request, produce pytest unit tests for the NEW or MODIFIED code.

Respond with JSON:
{
    "analysis": "Brief reasoning",
    "tests": [
        {"path": "tests/test_<module>.py", "content": "full file content"}
    ],
    "commit_message": "Short commit message"
}

Rules:
- Test the CONTRACT (inputs -> outputs, error paths), not implementation details
- Use pytest style: plain functions, assert statements, parametrize when helpful
- If existing test file targets the same module, append to it rather than creating a new file
- Do NOT test trivial getters, __init__, private methods
- Do NOT write tests that require network/IO — mock dependencies
- If nothing sensible to test, return empty `tests` array with explanation in `analysis`
- Only output tests for source files, never test `tests/*` themselves"""


class TestGenAgent(Agent):
    def run(self, pr_number: int) -> dict:
        pr = self.github.get_pull_request(pr_number)
        files = self.github.get_pr_files(pr_number)

        source_files = [
            f for f in files
            if f["filename"].endswith(".py")
            and not f["filename"].startswith("tests/")
            and f["status"] != "removed"
        ]

        if not source_files:
            return {"success": True, "skipped": True, "reason": "no python source files changed"}

        diff = self.github.get_pr_diff(pr_number)
        file_contents = ""
        for f in source_files[:5]:
            content = self.github.get_file_content(f["filename"], ref=pr.head.ref)
            if content:
                file_contents += f"\n\n--- {f['filename']} ---\n{content}"

        user_prompt = f"""PR title: {pr.title}

Changed source files:
{chr(10).join("- " + f["filename"] for f in source_files)}

Current content of changed files:
{file_contents[:15000]}

Diff:
{diff[:10000]}

Generate tests."""

        response = self.llm.chat(SYSTEM_PROMPT, user_prompt)
        parsed = self._parse_response(response)

        if not parsed:
            return {"success": False, "error": "Failed to parse test gen response"}

        if not parsed.tests:
            return {"success": True, "skipped": True, "reason": parsed.analysis}

        commit_sha = self._commit_tests(pr.head.ref, parsed)
        if not commit_sha:
            return {"success": False, "error": "Failed to commit tests"}

        return {
            "success": True,
            "pr_number": pr_number,
            "tests_added": len(parsed.tests),
            "commit": commit_sha,
        }

    def _parse_response(self, response: str) -> TestGenResponse | None:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(response[start:end])
                return TestGenResponse.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error("Failed to parse test gen response: %s", e)
        return None

    def _commit_tests(self, branch: str, parsed: TestGenResponse) -> str | None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token = self.github.get_installation_token()
            repo_url = f"https://x-access-token:{token}@github.com/{self.github.repo.full_name}.git"
            repo = Repo.clone_from(repo_url, tmpdir, branch=branch)

            for test in parsed.tests:
                file_path = Path(tmpdir) / test.path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(test.content)
                repo.index.add([test.path])

            if not repo.index.diff("HEAD"):
                return None

            msg = f"{parsed.commit_message} {SKIP_COMMIT_TAG}"
            commit = repo.index.commit(msg)
            repo.remote("origin").push(branch)
            return commit.hexsha[:7]
