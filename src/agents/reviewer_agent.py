import json
import re

from src.config import Settings
from src.github_client import GitHubClient
from src.llm_client import LLMClient


SYSTEM_PROMPT = """You are an expert code reviewer. Your task is to review pull request changes and verify they correctly implement the requirements from the linked issue.

You will receive:
1. The original issue requirements
2. The PR diff (code changes)
3. CI/CD check results (if available)

You must respond with a JSON object containing:
{
    "approved": true | false,
    "summary": "Brief summary of your review",
    "issues": [
        {
            "severity": "critical" | "major" | "minor" | "suggestion",
            "description": "Description of the issue",
            "file": "path/to/file (optional)",
            "line": line_number (optional)
        }
    ],
    "meets_requirements": true | false,
    "requirements_feedback": "Feedback on how well the PR meets the issue requirements"
}

Review criteria:
1. Does the code correctly implement the issue requirements?
2. Is the code clean and readable?
3. Are there any bugs or logic errors?
4. Are there any security concerns?
5. Do CI checks pass?

Be constructive and specific in your feedback. If there are no issues, approve the PR."""


class ReviewerAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.github = GitHubClient(settings)
        self.llm = LLMClient(settings)

    def run(self, pr_number: int) -> dict:
        pr = self.github.get_pull_request(pr_number)

        issue_number = self._extract_issue_number(pr.body or "")
        issue_content = ""
        if issue_number:
            issue = self.github.get_issue(issue_number)
            issue_content = f"Issue #{issue_number}: {issue.title}\n\n{issue.body or ''}"

        diff = self.github.get_pr_diff(pr_number)
        check_runs = self.github.get_check_runs(pr_number)

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

Please review the changes and provide your assessment."""

        response = self.llm.chat(SYSTEM_PROMPT, user_prompt)
        review = self._parse_response(response)

        if not review:
            return {"success": False, "error": "Failed to parse review"}

        self._post_review(pr_number, review)

        return {
            "success": True,
            "approved": review.get("approved", False),
            "summary": review.get("summary", ""),
            "issues_count": len(review.get("issues", [])),
        }

    def _extract_issue_number(self, body: str) -> int | None:
        patterns = [
            r"#(\d+)",
            r"closes #(\d+)",
            r"fixes #(\d+)",
            r"resolves #(\d+)",
        ]
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

    def _post_review(self, pr_number: int, review: dict) -> None:
        summary = review.get("summary", "Review completed")
        issues = review.get("issues", [])
        approved = review.get("approved", False)
        meets_requirements = review.get("meets_requirements", False)

        body_parts = ["## AI Code Review\n"]
        body_parts.append(f"**Status:** {'✅ Approved' if approved else '❌ Changes Requested'}\n")
        body_parts.append(f"**Requirements Met:** {'✅ Yes' if meets_requirements else '❌ No'}\n")
        body_parts.append(f"\n### Summary\n{summary}\n")

        if review.get("requirements_feedback"):
            body_parts.append(f"\n### Requirements Analysis\n{review['requirements_feedback']}\n")

        if issues:
            body_parts.append("\n### Issues Found\n")
            for issue in issues:
                severity = issue.get("severity", "minor").upper()
                desc = issue.get("description", "")
                file_info = ""
                if issue.get("file"):
                    file_info = f" (`{issue['file']}"
                    if issue.get("line"):
                        file_info += f":{issue['line']}"
                    file_info += "`)"
                body_parts.append(f"- **[{severity}]** {desc}{file_info}\n")

        body = "".join(body_parts)

        self.github.add_pr_comment(pr_number, body)
