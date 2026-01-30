import hashlib
import hmac
import logging
import re
import time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from src.agents.code_agent import CodeAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.config import get_settings
from src.github_client import GitHubClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ITERATION_MARKER = "[SDLC-ITERATION:"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SDLC Agent server started")
    yield
    logger.info("SDLC Agent server stopped")


app = FastAPI(title="SDLC Agent", lifespan=lifespan)


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature or not secret:
        return not secret

    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_iteration_count(github: GitHubClient, pr_number: int) -> int:
    comments = github.get_pr_comments(pr_number)
    for comment in reversed(comments):
        body = comment.get("body", "")
        if ITERATION_MARKER in body:
            match = re.search(r"\[SDLC-ITERATION:(\d+)\]", body)
            if match:
                return int(match.group(1))
    return 0


def extract_issue_number(body: str) -> int | None:
    patterns = [r"#(\d+)", r"closes #(\d+)", r"fixes #(\d+)", r"resolves #(\d+)"]
    for pattern in patterns:
        match = re.search(pattern, body.lower())
        if match:
            return int(match.group(1))
    return None


def process_issue(issue_number: int, repo: str):
    logger.info(f"Processing issue #{issue_number} in {repo}")
    try:
        settings = get_settings()
        settings.target_repo = repo
        agent = CodeAgent(settings)
        result = agent.run(issue_number)
        logger.info(f"Issue #{issue_number} result: {result}")
    except Exception as e:
        logger.error(f"Error processing issue #{issue_number}: {e}")


def process_pr_review(pr_number: int, repo: str):
    logger.info(f"Reviewing PR #{pr_number} in {repo}")
    try:
        settings = get_settings()
        settings.target_repo = repo

        github = GitHubClient(settings)
        pr = github.get_pull_request(pr_number)

        iteration = get_iteration_count(github, pr_number) + 1
        logger.info(f"PR #{pr_number} iteration: {iteration}/{settings.max_iterations}")

        if iteration > settings.max_iterations:
            logger.warning(f"PR #{pr_number} reached max iterations ({settings.max_iterations}), stopping")
            github.add_pr_comment(
                pr_number,
                f"⚠️ **Max iterations reached ({settings.max_iterations})**. Stopping automatic fixes."
            )
            return

        agent = ReviewerAgent(settings)
        result = agent.run(pr_number)
        logger.info(f"PR #{pr_number} review result: {result}")

        github.add_pr_comment(pr_number, f"<!-- {ITERATION_MARKER}{iteration}] -->")

        if result.get("success") and not result.get("approved", False):
            issue_number = extract_issue_number(pr.body or "")
            if issue_number and result.get("issues_count", 0) > 0:
                logger.info(f"PR #{pr_number} not approved, triggering fix cycle for issue #{issue_number}")
                time.sleep(2)
                process_issue(issue_number, repo)
            else:
                logger.info(f"PR #{pr_number} not approved but no linked issue found or no issues to fix")
        elif result.get("approved"):
            logger.info(f"PR #{pr_number} approved!")

    except Exception as e:
        logger.error(f"Error reviewing PR #{pr_number}: {e}")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
):
    settings = get_settings()
    payload = await request.body()

    if not verify_signature(payload, x_hub_signature_256 or "", settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    repo = data.get("repository", {}).get("full_name", "")

    if not repo:
        return {"status": "ignored", "reason": "no repository"}

    if x_github_event == "issues":
        action = data.get("action")
        if action in ("opened", "labeled"):
            issue_number = data.get("issue", {}).get("number")
            if issue_number:
                background_tasks.add_task(process_issue, issue_number, repo)
                return {"status": "processing", "event": "issue", "number": issue_number}

    elif x_github_event == "pull_request":
        action = data.get("action")
        if action in ("opened", "synchronize"):
            pr_number = data.get("pull_request", {}).get("number")
            if pr_number:
                background_tasks.add_task(process_pr_review, pr_number, repo)
                return {"status": "processing", "event": "pull_request", "number": pr_number}

    return {"status": "ignored", "event": x_github_event}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
