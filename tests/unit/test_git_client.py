"""Tests for GitClient and git provider factory (Phase 7)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from regulatory_agent_kit.exceptions import GitError
from regulatory_agent_kit.tools.git_client import GitClient
from regulatory_agent_kit.tools.git_provider import (
    GitHubClient,
    GitLabClient,
    create_git_provider,
)


# ======================================================================
# GitClient — subprocess mocking
# ======================================================================


class TestGitClient:
    """Test the async GitClient wrapper."""

    async def test_clone_calls_subprocess(self) -> None:
        client = GitClient()
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"Cloning...\n", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await client.clone("https://github.com/org/repo.git", "/tmp/dest")

        assert result.returncode == 0
        assert "Cloning" in result.stdout
        # First positional arg to create_subprocess_exec should be "git"
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "git"
        assert "clone" in call_args

    async def test_commit_calls_subprocess(self) -> None:
        client = GitClient()
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"[main abc1234] msg\n", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.commit("/repo", "test commit")

        assert result.returncode == 0

    async def test_non_zero_exit_raises_git_error(self) -> None:
        client = GitClient()
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"fatal: not a git repo")
        mock_proc.returncode = 128

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            pytest.raises(GitError, match="failed"),
        ):
            await client.diff("/not-a-repo")

    async def test_create_branch(self) -> None:
        client = GitClient()
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"Switched to new branch\n", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.create_branch("/repo", "feature/x")

        assert result.returncode == 0

    async def test_token_injection(self) -> None:
        client = GitClient(token="ghp_secret")
        url = client._inject_token("https://github.com/org/repo.git")
        assert "x-access-token:ghp_secret@" in url

    async def test_no_token_injection_for_ssh(self) -> None:
        client = GitClient(token="ghp_secret")
        url = client._inject_token("git@github.com:org/repo.git")
        assert url == "git@github.com:org/repo.git"

    async def test_add(self) -> None:
        client = GitClient()
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.add("/repo", ["file1.py", "file2.py"])

        assert result.returncode == 0

    async def test_push(self) -> None:
        client = GitClient()
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.push("/repo", "origin", "main")

        assert result.returncode == 0

    async def test_log(self) -> None:
        client = GitClient()
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"abc1234 msg\n", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.log("/repo", n=5)

        assert result.returncode == 0


# ======================================================================
# create_git_provider factory
# ======================================================================


class TestCreateGitProvider:
    """Test the git provider factory function."""

    def test_github_url_returns_github_client(self) -> None:
        client = create_git_provider("https://github.com/org/repo.git")
        assert isinstance(client, GitHubClient)

    def test_gitlab_url_returns_gitlab_client(self) -> None:
        client = create_git_provider("https://gitlab.com/org/repo.git")
        assert isinstance(client, GitLabClient)

    def test_unsupported_host_raises(self) -> None:
        with pytest.raises(Exception, match="Unsupported"):
            create_git_provider("https://bitbucket.org/org/repo.git")

    def test_bad_url_raises(self) -> None:
        with pytest.raises(Exception):
            create_git_provider("https://github.com/")
