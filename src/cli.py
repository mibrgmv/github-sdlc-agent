import sys

import click

from src.agents.code_agent import CodeAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.config import get_settings


@click.group()
def cli():
    pass


@cli.command()
@click.argument("issue_number", type=int)
@click.option("--repo", envvar="TARGET_REPO", help="Target repository (owner/repo)")
def solve(issue_number: int, repo: str | None):
    settings = get_settings()
    if repo:
        settings.target_repo = repo

    if not settings.github_token:
        click.echo("Error: GITHUB_TOKEN is required", err=True)
        sys.exit(1)
    if not settings.openai_api_key:
        click.echo("Error: OPENAI_API_KEY is required", err=True)
        sys.exit(1)
    if not settings.target_repo:
        click.echo("Error: TARGET_REPO is required", err=True)
        sys.exit(1)

    click.echo(f"Processing issue #{issue_number} in {settings.target_repo}...")

    agent = CodeAgent(settings)
    result = agent.run(issue_number)

    if result.get("success"):
        click.echo(f"Success! PR {result['action']}: {result['pr_url']}")
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("pr_number", type=int)
@click.option("--repo", envvar="TARGET_REPO", help="Target repository (owner/repo)")
def review(pr_number: int, repo: str | None):
    settings = get_settings()
    if repo:
        settings.target_repo = repo

    if not settings.github_token:
        click.echo("Error: GITHUB_TOKEN is required", err=True)
        sys.exit(1)
    if not settings.openai_api_key:
        click.echo("Error: OPENAI_API_KEY is required", err=True)
        sys.exit(1)
    if not settings.target_repo:
        click.echo("Error: TARGET_REPO is required", err=True)
        sys.exit(1)

    click.echo(f"Reviewing PR #{pr_number} in {settings.target_repo}...")

    agent = ReviewerAgent(settings)
    result = agent.run(pr_number)

    if result.get("success"):
        status = "approved" if result.get("approved") else "changes requested"
        click.echo(f"Review complete: {status}")
        click.echo(f"Summary: {result.get('summary', 'N/A')}")
        if result.get("issues_count", 0) > 0:
            click.echo(f"Issues found: {result['issues_count']}")
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
