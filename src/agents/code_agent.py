import json
import re
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
4. BLOCKING issues from code review that MUST be fixed

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
- PRIORITY: Fix all BLOCKING issues first — they prevent merge
- Write clean, readable code
- Follow existing code style in the repository
- Only modify files that are necessary
- Ensure code is functional and complete"""


class CodeAgent:
    def __init__(self, settings: Settings, repo: str):
        self.settings = settings
        self.github = GitHubClient(settings, repo)
        self.llm = LLMClient(settings)

    def run(self, issue_number: int, force_new: bool = False) -> dict:
        issue = self.github.get_issue(issue_number)

        existing_prs = []
        if not force_new:
            existing_prs = self.github.get_open_prs_for_issue(issue_number)

        blocking_issues = []
        branch_name = f"issue-{issue_number}"

        if existing_prs:
            pr = existing_prs[0]
            blocking_issues = self._parse_blocking_issues(pr.number)
            branch_name = pr.head.ref
        elif force_new:
            import time
            branch_name = f"issue-{issue_number}-{int(time.time())}"

        repo_files = self.github.get_repo_files()
        file_structure = "\n".join(repo_files[:100])

        relevant_files = self._get_relevant_files(issue.title, issue.body or "", repo_files, blocking_issues)
        file_contents = ""
        for path in relevant_files[:10]:
            content = self.github.get_file_content(path)
            if content:
                file_contents += f"\n\n--- {path} ---\n{content}"

        blocking_section = ""
        if blocking_issues:
            blocking_section = "\n\n⚠️ BLOCKING ISSUES TO FIX:\n"
            for issue_item in blocking_issues:
                severity = issue_item.get("severity", "ERROR")
                desc = issue_item.get("description", "")
                file = issue_item.get("file", "")
                line = issue_item.get("line", "")
                loc = f" ({file}:{line})" if file else ""
                blocking_section += f"- [{severity}] {desc}{loc}\n"

        user_prompt = f"""Issue #{issue_number}: {issue.title}

Description:
{issue.body or "No description provided"}

Repository structure:
{file_structure}

Relevant file contents:
{file_contents if file_contents else "No relevant files found"}
{blocking_section}
Please analyze the issue and provide the necessary code changes."""

        response = self.llm.chat(SYSTEM_PROMPT, user_prompt)
        changes = self._parse_response(response)

        if not changes or not changes.get("changes"):
            return {"success": False, "error": "Failed to generate changes"}

        result = self._apply_changes(changes, issue_number, branch_name, existing_prs)
        return result

    def _parse_blocking_issues(self, pr_number: int) -> list[dict]:
        comments = self.github.get_pr_comments(pr_number)
        blocking_issues = []

        for comment in reversed(comments):
            body = comment.get("body", "")
            if "## AI Code Review" not in body:
                continue

            in_blocking_section = False
            for line in body.split("\n"):
                if "🚫 Blocking Issues" in line:
                    in_blocking_section = True
                    continue
                if "💡 Suggestions" in line or line.startswith("### "):
                    in_blocking_section = False
                    continue

                if in_blocking_section and line.startswith("- **["):
                    issue = self._parse_issue_line(line)
                    if issue:
                        blocking_issues.append(issue)

            if blocking_issues:
                break

        return blocking_issues

    def _parse_issue_line(self, line: str) -> dict | None:
        match = re.match(r"- \*\*\[(\w+)\](?:\s*\[CI\])?\*\*\s+(.+)", line)
        if not match:
            return None

        severity = match.group(1)
        rest = match.group(2)

        file_match = re.search(r"\(`([^`]+)`\)$", rest)
        file = None
        line_num = None
        if file_match:
            file_info = file_match.group(1)
            rest = rest[:file_match.start()].strip()
            if ":" in file_info:
                file, line_str = file_info.rsplit(":", 1)
                try:
                    line_num = int(line_str)
                except ValueError:
                    file = file_info
            else:
                file = file_info

        return {
            "severity": severity,
            "description": rest,
            "file": file,
            "line": line_num,
        }

    def _get_relevant_files(self, title: str, body: str, all_files: list[str], blocking_issues: list[dict]) -> list[str]:
        relevant = set()

        for issue in blocking_issues:
            if issue.get("file"):
                relevant.add(issue["file"])

        keywords = (title + " " + body).lower().split()
        for f in all_files:
            f_lower = f.lower()
            if any(kw in f_lower for kw in keywords):
                relevant.add(f)
            elif f.endswith((".py", ".js", ".ts", ".yml", ".yaml", ".json", ".md")):
                relevant.add(f)

        return list(relevant)[:20]

    def _parse_response(self, response: str) -> dict:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass
        return {}

    def _apply_changes(self, changes: dict, issue_number: int, branch_name: str, existing_prs: list) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            token = self.github.get_installation_token()
            repo_url = f"https://x-access-token:{token}@github.com/{self.github.repo.full_name}.git"
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
