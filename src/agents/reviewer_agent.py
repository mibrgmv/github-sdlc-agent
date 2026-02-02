import json
import re
from src.config import Settings
from src.github_client import GitHubClient
from src.llm_client import LLMClient

BLOCKING_SEVERITIES = {"error", "requirement"}
NON_BLOCKING_SEVERITIES = {"refactor", "style", "suggestion"}

SYSTEM_PROMPT = """You are a pragmatic code reviewer. Focus on functionality over style.

Categorize issues by severity:

BLOCKING (use sparingly — only for real problems):
- "error" — actual bugs, crashes, security vulnerabilities, code that won't run
- "requirement" — core functionality missing (function doesn't exist, wrong return type, completely wrong behavior)

NON-BLOCKING (suggestions):
- "refactor" — code structure improvements
- "style" — naming, formatting
- "suggestion" — nice-to-have

IMPORTANT RULES:
1. If code implements the requested functionality and would work correctly — APPROVE
2. "requirement" is ONLY for missing core functionality, NOT for style preferences like "LeetCode-style" or test format
3. If tests exist and test the core functionality — that's sufficient, don't nitpick test style
4. Prefer to approve with suggestions rather than block on minor issues

Respond with JSON:
{
    "summary": "Brief summary",
    "issues": [
        {
            "severity": "error" | "requirement" | "refactor" | "style" | "suggestion",
            "description": "Description",
            "file": "path (optional)",
            "line": number (optional)
        }
    ],
    "meets_requirements": true | false
}

When in doubt, use NON-BLOCKING severity."""


class ReviewerAgent:
    def __init__(self, settings: Settings, repo: str):
        self.settings = settings
        self.github = GitHubClient(settings, repo)
        self.llm = LLMClient(settings)

    def run(self, pr_number: int, iteration: int = 0) -> dict:
        pr = self.github.get_pull_request(pr_number)

        issue_number = self._extract_issue_number(pr.body or "")
        issue_content = ""
        if issue_number:
            issue = self.github.get_issue(issue_number)
            issue_content = f"Issue #{issue_number}: {issue.title}\n\n{issue.body or ''}"

        diff = self.github.get_pr_diff(pr_number)
        check_runs = self.github.get_check_runs(pr_number)

        ci_issues = self._check_ci_status(check_runs)
        ci_passed = len(ci_issues) == 0

        ci_status = "No CI checks found"
        if check_runs:
            ci_parts = []
            for run in check_runs:
                status = run.get("conclusion") or run.get("status", "unknown")
                ci_parts.append(f"- {run['name']}: {status}")
            ci_status = "\n".join(ci_parts)

        user_prompt = f"""Pull Request: {pr.title}

Original Issue Requirements:
{issue_content if issue_content else "No linked issue found"}

Code Changes (Diff):
{diff[:15000]}

CI/CD Status:
{ci_status}

Review the changes. Remember: approve if core functionality works, don't block on style."""

        response = self.llm.chat(SYSTEM_PROMPT, user_prompt)
        review = self._parse_response(response)

        if not review:
            return {"success": False, "error": "Failed to parse review"}

        issues = review.get("issues", [])
        issues.extend(ci_issues)
        review["issues"] = issues

        blocking = [i for i in issues if i.get("severity") in BLOCKING_SEVERITIES]
        non_blocking = [i for i in issues if i.get("severity") in NON_BLOCKING_SEVERITIES]

        approved = len(blocking) == 0
        review["approved"] = approved
        review["blocking_count"] = len(blocking)
        review["non_blocking_count"] = len(non_blocking)

        self._post_review(pr_number, review, iteration, ci_passed)

        return {
            "success": True,
            "approved": approved,
            "summary": review.get("summary", ""),
            "issues_count": len(issues),
            "blocking_count": len(blocking),
            "non_blocking_count": len(non_blocking),
        }

    def _check_ci_status(self, check_runs: list[dict]) -> list[dict]:
        ci_issues = []
        for run in check_runs:
            conclusion = run.get("conclusion")
            if conclusion in ("failure", "timed_out", "cancelled"):
                ci_issues.append({
                    "severity": "error",
                    "description": f"CI check '{run['name']}' failed: {conclusion}",
                    "file": None,
                    "line": None,
                    "source": "ci",
                })
        return ci_issues

    def _extract_issue_number(self, body: str) -> int | None:
        patterns = [r"#(\d+)", r"closes #(\d+)", r"fixes #(\d+)", r"resolves #(\d+)"]
        for pattern in patterns:
            match = re.search(pattern, body.lower())
            if match:
                return int(match.group(1))
        return None

    def _parse_response(self, response: str) -> dict:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass
        return {}

    def _post_review(self, pr_number: int, review: dict, iteration: int, ci_passed: bool) -> None:
        summary = review.get("summary", "Review completed")
        issues = review.get("issues", [])
        approved = review.get("approved", False)
        meets_requirements = review.get("meets_requirements", False)

        blocking = [i for i in issues if i.get("severity") in BLOCKING_SEVERITIES]
        non_blocking = [i for i in issues if i.get("severity") in NON_BLOCKING_SEVERITIES]

        body_parts = [f"## AI Code Review (Iteration {iteration})\n"] if iteration else ["## AI Code Review\n"]
        body_parts.append(f"**Status:** {'✅ Approved' if approved else '❌ Changes Requested'}\n")
        body_parts.append(f"**Requirements Met:** {'✅ Yes' if meets_requirements else '❌ No'}\n")
        body_parts.append(f"**CI Status:** {'✅ Passed' if ci_passed else '❌ Failed'}\n")
        body_parts.append(f"\n### Summary\n{summary}\n")

        if blocking:
            body_parts.append("\n### 🚫 Blocking Issues (must fix)\n")
            for issue in blocking:
                severity = issue.get("severity", "error").upper()
                desc = issue.get("description", "")
                file_info = self._format_file_info(issue)
                source = " [CI]" if issue.get("source") == "ci" else ""
                body_parts.append(f"- **[{severity}]{source}** {desc}{file_info}\n")

        if non_blocking:
            body_parts.append("\n### 💡 Suggestions (non-blocking)\n")
            for issue in non_blocking:
                severity = issue.get("severity", "suggestion").upper()
                desc = issue.get("description", "")
                file_info = self._format_file_info(issue)
                body_parts.append(f"- **[{severity}]** {desc}{file_info}\n")

        self.github.add_pr_comment(pr_number, "".join(body_parts))

    def _format_file_info(self, issue: dict) -> str:
        if not issue.get("file"):
            return ""
        file_info = f" (`{issue['file']}"
        if issue.get("line"):
            file_info += f":{issue['line']}"
        return file_info + "`)"
