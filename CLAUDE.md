# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SDLC automation system with:
- **Code Agent** — reads GitHub Issues, generates code via LLM, creates PRs
- **AI Reviewer Agent** — reviews PRs, posts code review comments
- **Webhook Server** — FastAPI server that receives GitHub events and triggers agents

Three modes: Webhook Server (production), CLI (manual), GitHub Actions (CI/CD).

## Commands

```bash
# Install
pip install -r requirements.txt && pip install -e .

# Webhook server
docker-compose up server
# or: python -m uvicorn src.server:app --host 0.0.0.0 --port 8000

# CLI - Code Agent
python -m src.cli solve <issue_number> --repo owner/repo

# CLI - Reviewer
python -m src.cli review <pr_number> --repo owner/repo
```

## Architecture

- `src/server.py` — FastAPI webhook server, receives GitHub events
- `src/agents/code_agent.py` — clones repo, generates changes via LLM, creates PR
- `src/agents/reviewer_agent.py` — analyzes PR diff, posts review
- `src/github_client.py` — PyGithub wrapper with GitHub App support
- `src/llm_client.py` — OpenAI-compatible API client (Groq)
- `src/config.py` — settings from env vars
- `.github/workflows/` — alternative triggers via GitHub Actions

## Environment Variables

Required:
- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`
- `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_APP_INSTALLATION_ID`
- `GITHUB_WEBHOOK_SECRET` (for webhook server)
