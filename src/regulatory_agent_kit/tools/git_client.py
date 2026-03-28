"""Async subprocess wrapper around the git CLI."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from regulatory_agent_kit.exceptions import GitError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GitResult:
    """Structured result from a git command execution."""

    returncode: int
    stdout: str
    stderr: str


@dataclass
class GitClient:
    """Async git CLI wrapper.

    All operations delegate to ``git`` via ``asyncio.create_subprocess_exec``.
    A personal-access *token* can be injected for HTTPS authentication.
    """

    token: str | None = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run(
        self,
        *args: str,
        cwd: str | Path | None = None,
    ) -> GitResult:
        """Execute a git sub-process and return structured output.

        Raises:
            GitError: When the sub-process exits with a non-zero code.
        """
        cmd = ["git", *args]
        env_overrides: dict[str, str] | None = None
        if self.token is not None:
            env_overrides = {
                "GIT_ASKPASS": "echo",
                "GIT_TERMINAL_PROMPT": "0",
            }

        logger.debug("git %s (cwd=%s)", " ".join(args), cwd)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            env=env_overrides,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        result = GitResult(
            returncode=proc.returncode or 0,
            stdout=stdout_bytes.decode().strip(),
            stderr=stderr_bytes.decode().strip(),
        )

        if result.returncode != 0:
            msg = f"git {args[0]} failed (rc={result.returncode}): {result.stderr}"
            raise GitError(msg)

        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _inject_token(self, url: str) -> str:
        """Inject the token into an HTTPS URL for authentication."""
        if self.token and url.startswith("https://"):
            return url.replace("https://", f"https://x-access-token:{self.token}@", 1)
        return url

    async def clone(self, url: str, dest: str | Path) -> GitResult:
        """Clone a repository to *dest*."""
        authenticated_url = self._inject_token(url)
        return await self._run("clone", authenticated_url, str(dest))

    async def create_branch(self, repo_path: str | Path, branch_name: str) -> GitResult:
        """Create a new branch in *repo_path*."""
        return await self._run("checkout", "-b", branch_name, cwd=repo_path)

    async def checkout(self, repo_path: str | Path, branch: str) -> GitResult:
        """Check out an existing branch."""
        return await self._run("checkout", branch, cwd=repo_path)

    async def add(self, repo_path: str | Path, files: list[str]) -> GitResult:
        """Stage files for commit."""
        return await self._run("add", "--", *files, cwd=repo_path)

    async def commit(self, repo_path: str | Path, message: str) -> GitResult:
        """Create a commit with *message*."""
        return await self._run("commit", "-m", message, cwd=repo_path)

    async def push(
        self,
        repo_path: str | Path,
        remote: str = "origin",
        branch: str = "HEAD",
    ) -> GitResult:
        """Push the current branch to *remote*."""
        return await self._run("push", remote, branch, cwd=repo_path)

    async def diff(self, repo_path: str | Path) -> GitResult:
        """Return the diff of unstaged changes."""
        return await self._run("diff", cwd=repo_path)

    async def log(self, repo_path: str | Path, n: int = 10) -> GitResult:
        """Return the last *n* log entries (one-line format)."""
        return await self._run("log", "--oneline", f"-{n}", cwd=repo_path)
