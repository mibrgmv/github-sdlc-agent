# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SDLC automation system with two agents:
- **Code Agent** (CLI) — reads GitHub Issues, generates code, creates PRs
- **AI Reviewer Agent** — runs in GitHub Actions, reviews PRs

## Commands

```bash
# Install
pip install -r requirements.txt && pip install -e .

# Run Code Agent
python -m src.cli solve <issue_number> --repo owner/repo

# Run Reviewer
python -m src.cli review <pr_number> --repo owner/repo

# Docker
cd docker && ISSUE_NUMBER=1 docker-compose run code-agent
```

## Architecture

- `src/agents/code_agent.py` — clones repo, generates changes via LLM, pushes branch, creates PR
- `src/agents/reviewer_agent.py` — analyzes PR diff, checks CI status, posts review
- `src/github_client.py` — PyGithub wrapper for Issues, PRs, files
- `src/llm_client.py` — OpenAI API client
- `.github/workflows/` — triggers on issue creation and PR updates

## Environment Variables

Required: `GITHUB_TOKEN`, `OPENAI_API_KEY`, `TARGET_REPO`
