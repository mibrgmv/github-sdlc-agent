import logging
import re
import time
from src.agents.code_agent import CodeAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.config import Settings
from src.github_client import GitHubClient

logger = logging.getLogger(__name__)

ITERATION_MARKER = "[SDLC-ITERATION:"


def extract_issue_number(body: str) -> int | None:
    patterns = [r"#(\d+)", r"closes #(\d+)", r"fixes #(\d+)", r"resolves #(\d+)"]
    for pattern in patterns:
        match = re.search(pattern, body.lower())
        if match:
            return int(match.group(1))
    return None


def get_iteration_count(github: GitHubClient, pr_number: int) -> int:
    comments = github.get_pr_comments(pr_number)
    for comment in reversed(comments):
        body = comment.get("body", "")
        if ITERATION_MARKER in body:
            match = re.search(r"\[SDLC-ITERATION:(\d+)\]", body)
            if match:
                return int(match.group(1))
    return 0


def run_solve(settings: Settings, repo: str, issue_number: int) -> dict:
    agent = CodeAgent(settings, repo)
    return agent.run(issue_number)


def run_review(settings: Settings, repo: str, pr_number: int) -> dict:
    agent = ReviewerAgent(settings, repo)
    return agent.run(pr_number)


def run_cycle(settings: Settings, repo: str, issue_number: int, on_event=None) -> dict:
    def log(msg):
        if on_event:
            on_event(msg)
        logger.info(msg)

    github = GitHubClient(settings, repo)

    for iteration in range(1, settings.max_iterations + 1):
        log(f"Iteration {iteration}/{settings.max_iterations}")

        solve_result = run_solve(settings, repo, issue_number)
        if not solve_result.get("success"):
            return {"success": False, "error": solve_result.get("error"), "iteration": iteration}

        pr_number = solve_result["pr_number"]
        log(f"PR #{pr_number} {solve_result['action']}")

        time.sleep(2)

        review_result = run_review(settings, repo, pr_number)
        if not review_result.get("success"):
            return {"success": False, "error": review_result.get("error"), "iteration": iteration}

        github.add_pr_comment(pr_number, f"<!-- {ITERATION_MARKER}{iteration}] -->")

        if review_result.get("approved"):
            log(f"PR #{pr_number} approved!")
            return {
                "success": True,
                "approved": True,
                "pr_number": pr_number,
                "pr_url": solve_result["pr_url"],
                "iteration": iteration,
            }

        log(f"PR #{pr_number} not approved, issues: {review_result.get('issues_count', 0)}")

    github.add_pr_comment(
        pr_number,
        f"⚠️ **Max iterations reached ({settings.max_iterations})**. Stopping automatic fixes."
    )

    return {
        "success": True,
        "approved": False,
        "pr_number": pr_number,
        "pr_url": solve_result["pr_url"],
        "iteration": settings.max_iterations,
        "reason": "max_iterations_reached",
    }
