import hashlib
import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from src.config import get_settings
from src.github_client import GitHubClient
from src.runner import extract_issue_number, get_iteration_count, run_cycle, run_describe, run_review, run_test_gen

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SDLC Agent server started")
    yield
    logger.info("SDLC Agent server stopped")


app = FastAPI(title="SDLC Agent", lifespan=lifespan)


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature or not secret:
        return not secret
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def process_issue(issue_number: int, repo: str):
    logger.info(f"Processing issue #{issue_number} in {repo}")
    try:
        settings = get_settings()
        result = run_cycle(settings, repo, issue_number)
        logger.info(f"Issue #{issue_number} result: {result}")
    except Exception as e:
        logger.error(f"Error processing issue #{issue_number}: {e}")


def process_pr_describe(pr_number: int, repo: str):
    logger.info(f"Describing PR #{pr_number} in {repo}")
    try:
        settings = get_settings()
        if "pr_desc" not in settings.enabled_agents_set:
            return
        result = run_describe(settings, repo, pr_number)
        logger.info(f"PR #{pr_number} describe result: {result}")
    except Exception as e:
        logger.error(f"Error describing PR #{pr_number}: {e}")


def process_pr_test_gen(pr_number: int, repo: str):
    logger.info(f"Generating tests for PR #{pr_number} in {repo}")
    try:
        settings = get_settings()
        if "test_gen" not in settings.enabled_agents_set:
            return
        result = run_test_gen(settings, repo, pr_number)
        logger.info(f"PR #{pr_number} test_gen result: {result}")
    except Exception as e:
        logger.error(f"Error generating tests for PR #{pr_number}: {e}")


def process_pr_review(pr_number: int, repo: str):
    logger.info(f"Reviewing PR #{pr_number} in {repo}")
    try:
        settings = get_settings()
        github = GitHubClient(settings, repo)
        pr = github.get_pull_request(pr_number)

        iteration = get_iteration_count(github, pr_number)
        if iteration >= settings.max_iterations:
            logger.warning(f"PR #{pr_number} reached max iterations ({settings.max_iterations}), skipping")
            return

        result = run_review(settings, repo, pr_number)
        logger.info(f"PR #{pr_number} review result: {result}")

        if result.get("success") and not result.get("approved", False):
            issue_number = extract_issue_number(pr.body or "")
            if issue_number and result.get("issues_count", 0) > 0:
                logger.info(f"PR #{pr_number} not approved, triggering fix for issue #{issue_number}")
                process_issue(issue_number, repo)

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
        pr_number = data.get("pull_request", {}).get("number")

        if not pr_number:
            return {"status": "ignored", "reason": "no pr number"}

        if action == "opened":
            background_tasks.add_task(process_pr_describe, pr_number, repo)
            background_tasks.add_task(process_pr_test_gen, pr_number, repo)
            background_tasks.add_task(process_pr_review, pr_number, repo)
            return {"status": "processing", "event": "pull_request.opened", "number": pr_number}

        if action == "synchronize":
            background_tasks.add_task(process_pr_review, pr_number, repo)
            return {"status": "processing", "event": "pull_request.synchronize", "number": pr_number}

    return {"status": "ignored", "event": x_github_event}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
