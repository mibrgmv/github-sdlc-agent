import json
import os
import subprocess
import tempfile
from pathlib import Path

from git import Repo

from src.config import Settings
from src.github_client import GitHubClient
from src.llm_client import LLMClient


SYSTEM_PROMPT = """You are an expert software developer. Your task is to implement code changes based on GitHub issue requirements.

You will receive:
1. Issue title and description
2. Current repository file structure
3. Relevant file contents
4. Any previous review comments (if this is a revision)

You must respond with a JSON object containing:
{
    "analysis": "Brief analysis of what needs to be done",
    "changes": [
        {
            "path": "path/to/file",
            "action": "create" | "modify" | "delete",
            "content": "full file content (for create/modify)"
        }
    ],
    "commit_message": "Descriptive commit message",
    "pr_title": "Pull request title",
    "pr_body": "Pull request description"
}

Guidelines:
- Write clean, readable code without comments
- Follow existing code style in the repository
- Only modify files that are necessary
- Keep changes minimal and focused
- Ensure code is functional and complete"""


class CodeAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.github = GitHubClient(settings)
        self.llm = LLMClient(settings)

    def run(self, issue_number: int) -> dict:
        issue = self.github.get_issue(issue_number)

        existing_prs = self.github.get_open_prs_for_issue(issue_number)
        review_comments = ""
        branch_name = f"issue-{issue_number}"

        if existing_prs:
            pr = existing_prs[0]
            comments = self.github.get_pr_comments(pr.number)
            if comments:
                review_comments = "\n\nPrevious review comments:\n"
                for c in comments:
                    review_comments += f"- {c.get('user', 'unknown')}: {c.get('body', '')}\n"
            branch_name = pr.head.ref

        repo_files = self.github.get_repo_files()
        file_structure = "\n".join(repo_files[:100])

        relevant_files = self._get_relevant_files(issue.title, issue.body or "", repo_files)
        file_contents = ""
        for path in relevant_files[:10]:
            content = self.github.get_file_content(path)
            if content:
                file_contents += f"\n\n--- {path} ---\n{content}"

        user_prompt = f"""Issue #{issue_number}: {issue.title}

Description:
{issue.body or "No description provided"}

Repository structure:
{file_structure}

Relevant file contents:
{file_contents if file_contents else "No relevant files found"}
{review_comments}

Please analyze the issue and provide the necessary code changes."""

        response = self.llm.chat(SYSTEM_PROMPT, user_prompt)
        changes = self._parse_response(response)

        if not changes or not changes.get("changes"):
            return {"success": False, "error": "Failed to generate changes"}

        result = self._apply_changes(changes, issue_number, branch_name, existing_prs)
        return result

    def _get_relevant_files(
        self, title: str, body: str, all_files: list[str]
    ) -> list[str]:
        keywords = (title + " " + body).lower().split()
        relevant = []
        for f in all_files:
            f_lower = f.lower()
            if any(kw in f_lower for kw in keywords):
                relevant.append(f)
            elif f.endswith((".py", ".js", ".ts", ".yml", ".yaml", ".json", ".md")):
                relevant.append(f)
        return relevant[:20]

    def _parse_response(self, response: str) -> dict:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass
        return {}

    def _apply_changes(
        self,
        changes: dict,
        issue_number: int,
        branch_name: str,
        existing_prs: list,
    ) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_url = f"https://x-access-token:{self.settings.github_token}@github.com/{self.settings.target_repo}.git"
            repo = Repo.clone_from(repo_url, tmpdir)

            default_branch = self.github.get_default_branch()

            try:
                repo.git.checkout(branch_name)
            except Exception:
                repo.git.checkout("-b", branch_name)

            for change in changes.get("changes", []):
                file_path = Path(tmpdir) / change["path"]

                if change["action"] == "delete":
                    if file_path.exists():
                        file_path.unlink()
                        repo.index.remove([change["path"]])
                else:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(change["content"])
                    repo.index.add([change["path"]])

            if not repo.index.diff("HEAD") and not repo.untracked_files:
                return {"success": False, "error": "No changes to commit"}

            repo.index.commit(changes.get("commit_message", f"Fix issue #{issue_number}"))
            repo.remote("origin").push(branch_name, force=True)

        if existing_prs:
            pr = existing_prs[0]
            return {
                "success": True,
                "pr_number": pr.number,
                "pr_url": pr.html_url,
                "action": "updated",
            }

        pr = self.github.create_pull_request(
            title=changes.get("pr_title", f"Fix issue #{issue_number}"),
            body=changes.get("pr_body", f"Closes #{issue_number}") + f"\n\nCloses #{issue_number}",
            head=branch_name,
            base=default_branch,
        )

        return {
            "success": True,
            "pr_number": pr.number,
            "pr_url": pr.html_url,
            "action": "created",
        }
