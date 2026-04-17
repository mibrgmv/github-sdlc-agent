import json
import logging
import re

from pydantic import ValidationError

from src.config import Settings
from src.github_client import GitHubClient
from src.llm_client import LLMClient
from src.models import BLOCKING_SEVERITIES, NON_BLOCKING_SEVERITIES, ReviewIssue, ReviewResponse

logger = logging.getLogger(__name__)

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
2. "requirement" is ONLY for missing core functionality, NOT for style preferences
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

        for ci_issue in ci_issues:
            review.issues.append(ReviewIssue(**ci_issue))

        blocking = [i for i in review.issues if i.severity in BLOCKING_SEVERITIES]
        non_blocking = [i for i in review.issues if i.severity in NON_BLOCKING_SEVERITIES]
        review.approved = len(blocking) == 0

        self._post_review(pr_number, review, iteration, ci_passed)

        return {
            "success": True,
            "approved": review.approved,
            "summary": review.summary,
            "issues_count": len(review.issues),
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
        patterns = [
            r"closes #(\d+)",
            r"fixes #(\d+)",
            r"resolves #(\d+)",
            r"#(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, body.lower())
            if match:
                return int(match.group(1))
        return None

    def _parse_response(self, response: str) -> ReviewResponse | None:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(response[start:end])
                return ReviewResponse.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error("Failed to parse review response: %s", e)
        return None

    def _format_body(self, review: ReviewResponse, iteration: int, ci_passed: bool) -> str:
        header = f"## AI Code Review (Iteration {iteration})\n" if iteration else "## AI Code Review\n"
        parts = [header]
        parts.append(f"**Status:** {'✅ Approved' if review.approved else '❌ Changes Requested'}\n")
        parts.append(f"**Requirements Met:** {'✅ Yes' if review.meets_requirements else '❌ No'}\n")
        parts.append(f"**CI Status:** {'✅ Passed' if ci_passed else '❌ Failed'}\n")
        parts.append(f"\n### Summary\n{review.summary}\n")

        blocking = [i for i in review.issues if i.severity in BLOCKING_SEVERITIES]
        non_blocking = [i for i in review.issues if i.severity in NON_BLOCKING_SEVERITIES]

        if blocking:
            parts.append("\n### 🚫 Blocking Issues (must fix)\n")
            for issue in blocking:
                file_info = self._format_file_info(issue)
                source = " [CI]" if issue.source == "ci" else ""
                parts.append(f"- **[{issue.severity.upper()}]{source}** {issue.description}{file_info}\n")

        if non_blocking:
            parts.append("\n### 💡 Suggestions (non-blocking)\n")
            for issue in non_blocking:
                file_info = self._format_file_info(issue)
                parts.append(f"- **[{issue.severity.upper()}]** {issue.description}{file_info}\n")

        return "".join(parts)

    def _format_file_info(self, issue: ReviewIssue) -> str:
        if not issue.file:
            return ""
        info = f" (`{issue.file}"
        if issue.line:
            info += f":{issue.line}"
        return info + "`)"

    def _post_review(self, pr_number: int, review: ReviewResponse, iteration: int, ci_passed: bool) -> None:
        event = "APPROVE" if review.approved else "REQUEST_CHANGES"
        body = self._format_body(review, iteration, ci_passed)
        self.github.create_pr_review(pr_number, body=body, event=event)
