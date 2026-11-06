import pytest
import respx
from httpx import Response

from compass.errors import (
    GitHubNotFoundError,
    GitHubPermissionError,
    GitHubRateLimitError,
    InputError,
)
from compass.tools.github_client import GitHubClient, parse_repo_url


def test_parse_repo_url_valid():
    assert parse_repo_url("https://github.com/owner/repo") == ("owner", "repo")
    assert parse_repo_url("https://github.com/owner/repo/") == ("owner", "repo")
    assert parse_repo_url("https://github.com/owner/repo.git") == ("owner", "repo")
    assert parse_repo_url("github.com/owner/repo") == ("owner", "repo")


def test_parse_repo_url_invalid():
    with pytest.raises(InputError):
        parse_repo_url("https://gitlab.com/owner/repo")
    with pytest.raises(InputError):
        parse_repo_url("https://github.com/owner")
    with pytest.raises(InputError):
        parse_repo_url("malformed")


@respx.mock
def test_get_repository_success():
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json={"name": "repo", "stargazers_count": 10})
    )
    with GitHubClient() as client:
        repo = client.get_repository("owner", "repo")
        assert repo["name"] == "repo"
        assert repo["stargazers_count"] == 10


@respx.mock
def test_get_repository_404():
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(404)
    )
    with GitHubClient() as client:
        with pytest.raises(GitHubNotFoundError):
            client.get_repository("owner", "repo")


@respx.mock
def test_get_repository_rate_limit():
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "12345"})
    )
    with GitHubClient() as client:
        with pytest.raises(GitHubRateLimitError):
            client.get_repository("owner", "repo")


@respx.mock
def test_get_file_text_success():
    respx.get("https://api.github.com/repos/owner/repo/contents/README.md").mock(
        return_value=Response(200, text="hello world")
    )
    with GitHubClient() as client:
        content = client.get_file_text("owner", "repo", "README.md")
        assert content == "hello world"


@respx.mock
def test_get_file_text_404():
    respx.get("https://api.github.com/repos/owner/repo/contents/README.md").mock(
        return_value=Response(404)
    )
    with GitHubClient() as client:
        content = client.get_file_text("owner", "repo", "README.md")
        assert content is None


@respx.mock
def test_get_issues_filters_prs():
    respx.get("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=Response(200, json=[
            {"number": 1, "title": "issue 1"},
            {"number": 2, "title": "pr 1", "pull_request": {}},
            {"number": 3, "title": "issue 2"},
        ])
    )
    with GitHubClient() as client:
        issues = client.get_issues("owner", "repo")
        assert len(issues) == 2
        assert issues[0]["number"] == 1
        assert issues[1]["number"] == 3
