from github import Auth, GithubException, GithubIntegration
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository

from src.config import Settings


class GitHubClient:
    def __init__(self, settings: Settings, repo: str):
        self.settings = settings
        self.gh = self._create_github_client()
        self.repo: Repository = self.gh.get_repo(repo)

    def _create_github_client(self):
        auth = Auth.AppAuth(
            int(self.settings.github_app_id),
            self.settings.github_app_private_key,
        )
        gi = GithubIntegration(auth=auth)

        if self.settings.github_app_installation_id:
            installation_id = int(self.settings.github_app_installation_id)
        else:
            installation = gi.get_installations()[0]
            installation_id = installation.id

        return gi.get_github_for_installation(installation_id)

    def get_installation_token(self) -> str:
        auth = Auth.AppAuth(
            int(self.settings.github_app_id),
            self.settings.github_app_private_key,
        )
        gi = GithubIntegration(auth=auth)

        if self.settings.github_app_installation_id:
            installation_id = int(self.settings.github_app_installation_id)
        else:
            installation = gi.get_installations()[0]
            installation_id = installation.id

        token = gi.get_access_token(installation_id)
        return token.token

    def get_issue(self, issue_number: int) -> Issue:
        return self.repo.get_issue(issue_number)

    def get_pull_request(self, pr_number: int) -> PullRequest:
        return self.repo.get_pull(pr_number)

    def create_pull_request(
        self, title: str, body: str, head: str, base: str = "main"
    ) -> PullRequest:
        return self.repo.create_pull(title=title, body=body, head=head, base=base)

    def get_pr_diff(self, pr_number: int) -> str:
        pr = self.get_pull_request(pr_number)
        files = pr.get_files()
        diff_parts = []
        for file in files:
            diff_parts.append(f"File: {file.filename}")
            diff_parts.append(f"Status: {file.status}")
            if file.patch:
                diff_parts.append(file.patch)
            diff_parts.append("")
        return "\n".join(diff_parts)

    def get_pr_comments(self, pr_number: int) -> list[dict]:
        pr = self.get_pull_request(pr_number)
        comments = []
        for comment in pr.get_issue_comments():
            comments.append({"user": comment.user.login, "body": comment.body})
        for comment in pr.get_review_comments():
            comments.append({
                "user": comment.user.login,
                "body": comment.body,
                "path": comment.path,
                "line": comment.line,
            })
        return comments

    def add_pr_comment(self, pr_number: int, body: str) -> None:
        pr = self.get_pull_request(pr_number)
        pr.create_issue_comment(body)

    def create_pr_review(
        self, pr_number: int, body: str, event: str = "COMMENT"
    ) -> None:
        pr = self.get_pull_request(pr_number)
        pr.create_review(body=body, event=event)

    def get_check_runs(self, pr_number: int) -> list[dict]:
        pr = self.get_pull_request(pr_number)
        commits = list(pr.get_commits())
        if not commits:
            return []
        last_commit = commits[-1]
        check_runs = last_commit.get_check_runs()
        results = []
        for run in check_runs:
            results.append({
                "name": run.name,
                "status": run.status,
                "conclusion": run.conclusion,
                "output": run.output,
            })
        return results

    def get_open_prs_for_issue(self, issue_number: int) -> list[PullRequest]:
        prs = []
        for pr in self.repo.get_pulls(state="open"):
            if f"#{issue_number}" in (pr.body or ""):
                prs.append(pr)
        return prs

    def get_repo_files(self, path: str = "", ref: str = "main") -> list[str]:
        try:
            contents = self.repo.get_contents(path, ref=ref)
            files = []
            if isinstance(contents, list):
                for content in contents:
                    if content.type == "dir":
                        files.extend(self.get_repo_files(content.path, ref))
                    else:
                        files.append(content.path)
            else:
                files.append(contents.path)
            return files
        except GithubException:
            return []

    def get_file_content(self, path: str, ref: str = "main") -> str | None:
        try:
            content = self.repo.get_contents(path, ref=ref)
            if isinstance(content, list):
                return None
            return content.decoded_content.decode("utf-8")
        except GithubException:
            return None

    def get_default_branch(self) -> str:
        return self.repo.default_branch
