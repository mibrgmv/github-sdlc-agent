import hashlib
import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from src.agents.code_agent import CodeAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.config import get_settings

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

    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


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
        agent = ReviewerAgent(settings)
        result = agent.run(pr_number)
        logger.info(f"PR #{pr_number} review result: {result}")
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
