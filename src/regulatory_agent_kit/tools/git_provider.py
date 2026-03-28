"""Git hosting provider clients (GitHub, GitLab) behind a common Protocol."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse

import httpx

from regulatory_agent_kit.exceptions import ToolError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class GitProviderClient(Protocol):
    """Minimal interface for interacting with a git hosting provider."""

    async def create_pull_request(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict[str, Any]:
        """Create a pull/merge request and return provider-specific metadata."""
        ...  # pragma: no cover

    async def add_comment(self, *, pr_id: int | str, body: str) -> dict[str, Any]:
        """Add a comment to an existing pull/merge request."""
        ...  # pragma: no cover

    async def get_pr_status(self, *, pr_id: int | str) -> dict[str, Any]:
        """Return the current status/checks of a pull/merge request."""
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# GitHub implementation
# ---------------------------------------------------------------------------


@dataclass
class GitHubClient:
    """GitHub REST API v3 client for pull-request operations."""

    owner: str
    repo: str
    token: str = field(default="", repr=False)
    base_url: str = "https://api.github.com"

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def create_pull_request(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict[str, Any]:
        """Create a GitHub pull request."""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls"
        payload = {"title": title, "body": body, "head": head, "base": base}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    async def add_comment(self, *, pr_id: int | str, body: str) -> dict[str, Any]:
        """Add a comment to a GitHub pull request."""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/issues/{pr_id}/comments"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={"body": body}, headers=self._headers())
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    async def get_pr_status(self, *, pr_id: int | str) -> dict[str, Any]:
        """Get the status of a GitHub pull request."""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result


# ---------------------------------------------------------------------------
# GitLab implementation
# ---------------------------------------------------------------------------


@dataclass
class GitLabClient:
    """GitLab REST API v4 client for merge-request operations."""

    project_path: str
    token: str = field(default="", repr=False)
    base_url: str = "https://gitlab.com/api/v4"

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
        return headers

    @property
    def _encoded_path(self) -> str:
        return self.project_path.replace("/", "%2F")

    async def create_pull_request(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict[str, Any]:
        """Create a GitLab merge request."""
        url = f"{self.base_url}/projects/{self._encoded_path}/merge_requests"
        payload = {
            "title": title,
            "description": body,
            "source_branch": head,
            "target_branch": base,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    async def add_comment(self, *, pr_id: int | str, body: str) -> dict[str, Any]:
        """Add a note to a GitLab merge request."""
        url = f"{self.base_url}/projects/{self._encoded_path}/merge_requests/{pr_id}/notes"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={"body": body}, headers=self._headers())
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    async def get_pr_status(self, *, pr_id: int | str) -> dict[str, Any]:
        """Get the status of a GitLab merge request."""
        url = f"{self.base_url}/projects/{self._encoded_path}/merge_requests/{pr_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_git_provider(
    repo_url: str,
    *,
    token: str = "",
) -> GitProviderClient:
    """Return the appropriate provider client based on the repository URL.

    Raises:
        ToolError: When the hosting provider cannot be determined.
    """
    parsed = urlparse(repo_url)
    hostname = (parsed.hostname or "").lower()

    # Extract owner/repo from path (e.g., "/owner/repo.git")
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    min_path_parts = 2
    if len(parts) < min_path_parts:
        msg = f"Cannot parse owner/repo from URL: {repo_url}"
        raise ToolError(msg)

    owner = parts[0]
    repo = parts[1].removesuffix(".git")

    if "github" in hostname:
        return GitHubClient(owner=owner, repo=repo, token=token)

    if "gitlab" in hostname:
        project_path = f"{owner}/{repo}"
        return GitLabClient(project_path=project_path, token=token)

    msg = f"Unsupported git provider for host: {hostname}"
    raise ToolError(msg)
