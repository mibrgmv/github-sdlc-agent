import sys
import click
from src.config import get_settings
from src.runner import run_solve, run_review, run_cycle


def validate_settings(settings):
    if not settings.github_app_id or not settings.github_app_private_key:
        click.echo("Error: GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY_PATH are required", err=True)
        sys.exit(1)
    if not settings.openai_api_key:
        click.echo("Error: OPENAI_API_KEY is required", err=True)
        sys.exit(1)


@click.group()
def cli():
    pass


@cli.command()
@click.argument("issue_number", type=int)
@click.option("--repo", required=True, help="Target repository (owner/repo)")
@click.option("--auto", is_flag=True, help="Run full cycle with review iterations")
@click.option("--new", is_flag=True, help="Create new PR instead of updating existing")
def solve(issue_number: int, repo: str, auto: bool, new: bool):
    settings = get_settings()
    validate_settings(settings)

    if auto:
        click.echo(f"Running full cycle for issue #{issue_number} in {repo}...")
        result = run_cycle(settings, repo, issue_number, on_event=click.echo, force_new=new)

        if result.get("approved"):
            click.echo(f"Success! PR approved: {result['pr_url']} (iterations: {result['iteration']})")
        elif result.get("reason") == "max_iterations_reached":
            click.echo(f"Max iterations reached. PR: {result['pr_url']}")
        else:
            click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
    else:
        click.echo(f"Processing issue #{issue_number} in {repo}...")
        result = run_solve(settings, repo, issue_number, force_new=new)

        if result.get("success"):
            click.echo(f"Success! PR {result['action']}: {result['pr_url']}")
        else:
            click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)


@cli.command()
@click.argument("pr_number", type=int)
@click.option("--repo", required=True, help="Target repository (owner/repo)")
def review(pr_number: int, repo: str):
    settings = get_settings()
    validate_settings(settings)

    click.echo(f"Reviewing PR #{pr_number} in {repo}...")
    result = run_review(settings, repo, pr_number)

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
