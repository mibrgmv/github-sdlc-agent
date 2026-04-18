import json
import logging

from pydantic import ValidationError

from src.agents.base import Agent
from src.models import PRDescriptionResponse

logger = logging.getLogger(__name__)

MIN_BODY_LENGTH = 50
AUTO_MARKER = "<!-- sdlc-agent:pr-desc -->"

SYSTEM_PROMPT = """You write concise, informative GitHub Pull Request descriptions.

You receive:
- PR title
- List of changed files
- Diff
- Linked issue (if any)

Respond with JSON:
{
    "summary": "One-line summary for logs",
    "body": "Markdown body for the PR description"
}

Body structure:
## Summary
<2-3 sentences: what and why>

## Changes
- <bullet per meaningful change>

## Testing
<how this was or should be tested, or 'N/A' if unclear>

Rules:
- Keep it short. Prefer bullets over prose.
- Do not invent features not present in the diff.
- Do not include a 'Closes #N' line — the caller will append it."""


class PRDescAgent(Agent):
    def run(self, pr_number: int, force: bool = False) -> dict:
        pr = self.github.get_pull_request(pr_number)

        existing = pr.body or ""
        if not force and len(existing) >= MIN_BODY_LENGTH and AUTO_MARKER not in existing:
            return {"success": True, "skipped": True, "reason": "body already written"}

        diff = self.github.get_pr_diff(pr_number)
        files = self.github.get_pr_files(pr_number)
        file_list = "\n".join(f"- {f['filename']} ({f['status']})" for f in files)

        user_prompt = f"""PR title: {pr.title}

Changed files:
{file_list}

Diff:
{diff[:12000]}

Write a PR description."""

        response = self.llm.chat(SYSTEM_PROMPT, user_prompt)
        parsed = self._parse_response(response)

        if not parsed:
            return {"success": False, "error": "Failed to parse description"}

        body = f"{parsed.body}\n\n{AUTO_MARKER}"
        self.github.update_pull_request(pr_number, body=body)

        return {
            "success": True,
            "pr_number": pr_number,
            "summary": parsed.summary,
        }

    def _parse_response(self, response: str) -> PRDescriptionResponse | None:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(response[start:end])
                return PRDescriptionResponse.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error("Failed to parse PR description response: %s", e)
        return None
