"""Sandboxed test runner via Docker containers."""

from __future__ import annotations

import ast
import asyncio
import logging
from dataclasses import dataclass, field

from regulatory_agent_kit.exceptions import ToolError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Docker command builder (Command pattern)
# ---------------------------------------------------------------------------


class DockerCommand:
    """Fluent builder for docker run commands."""

    def __init__(self) -> None:
        self._flags: list[str] = []
        self._volumes: list[str] = []
        self._image: str = ""
        self._entrypoint: list[str] = []

    def rm(self) -> DockerCommand:
        """Add --rm flag."""
        self._flags.append("--rm")
        return self

    def network(self, mode: str) -> DockerCommand:
        """Set --network mode."""
        self._flags.append(f"--network={mode}")
        return self

    def read_only(self) -> DockerCommand:
        """Add --read-only flag."""
        self._flags.append("--read-only")
        return self

    def memory(self, limit: str) -> DockerCommand:
        """Set --memory limit."""
        self._flags.append(f"--memory={limit}")
        return self

    def cpus(self, limit: str) -> DockerCommand:
        """Set --cpus limit."""
        self._flags.append(f"--cpus={limit}")
        return self

    def stop_timeout(self, seconds: int) -> DockerCommand:
        """Set --stop-timeout in seconds."""
        self._flags.append(f"--stop-timeout={seconds}")
        return self

    def volume(self, host: str, container: str, mode: str = "rw") -> DockerCommand:
        """Add a -v volume mount."""
        self._volumes.append(f"{host}:{container}:{mode}")
        return self

    def workdir(self, path: str) -> DockerCommand:
        """Set -w working directory."""
        self._flags.extend(["-w", path])
        return self

    def extra_flags(self, flags: list[str]) -> DockerCommand:
        """Append arbitrary extra flags."""
        self._flags.extend(flags)
        return self

    def image(self, name: str) -> DockerCommand:
        """Set the Docker image."""
        self._image = name
        return self

    def entrypoint(self, *args: str) -> DockerCommand:
        """Set the container entrypoint command."""
        self._entrypoint = list(args)
        return self

    def build(self) -> list[str]:
        """Build the final command list."""
        cmd = ["docker", "run", *self._flags]
        for vol in self._volumes:
            cmd.extend(["-v", vol])
        cmd.append(self._image)
        cmd.extend(self._entrypoint)
        return cmd


# ---------------------------------------------------------------------------
# Dangerous-import detection
# ---------------------------------------------------------------------------

_DANGEROUS_MODULES: frozenset[str] = frozenset({"os", "subprocess", "socket"})


def _check_dangerous_imports(source: str) -> list[str]:
    """Return a list of dangerous module names found in *source*.

    Uses ``ast.parse`` for reliable detection rather than regex.
    """
    violations: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _DANGEROUS_MODULES:
                    violations.append(top)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in _DANGEROUS_MODULES:
                violations.append(top)

    return violations


# ---------------------------------------------------------------------------
# Structured result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TestResult:
    """Structured result of a sandboxed test run."""

    passed: bool
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 300
_DEFAULT_IMAGE = "python:3.12-slim"
_DEFAULT_MEMORY_LIMIT = "512m"
_DEFAULT_CPU_LIMIT = "1"


@dataclass
class TestRunner:
    """Run tests inside a hardened Docker container.

    Security constraints applied to every container:
    - ``--network=none`` (no network access)
    - ``--read-only`` (immutable root filesystem)
    - ``--memory=512m`` (memory cap)
    - ``--cpus=1`` (CPU cap)
    """

    image: str = _DEFAULT_IMAGE
    timeout: int = _DEFAULT_TIMEOUT
    memory_limit: str = _DEFAULT_MEMORY_LIMIT
    cpu_limit: str = _DEFAULT_CPU_LIMIT
    extra_docker_flags: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_tests(
        self,
        test_dir: str,
        *,
        image: str | None = None,
        timeout: int | None = None,
    ) -> TestResult:
        """Run ``pytest`` inside a Docker container against *test_dir*.

        Raises:
            ToolError: When docker itself fails to start.
        """
        effective_image = image or self.image
        effective_timeout = timeout or self.timeout
        cmd = self._build_command(test_dir, effective_image)

        logger.info(
            "Running tests: %s (timeout=%ds)",
            " ".join(cmd),
            effective_timeout,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=effective_timeout,
            )
        except TimeoutError:
            proc.kill()
            return TestResult(
                passed=False,
                returncode=-1,
                stdout="",
                stderr="",
                timed_out=True,
            )
        except FileNotFoundError as exc:
            msg = f"Docker not found: {exc}"
            raise ToolError(msg) from exc

        returncode = proc.returncode or 0
        return TestResult(
            passed=returncode == 0,
            returncode=returncode,
            stdout=stdout_bytes.decode(),
            stderr=stderr_bytes.decode(),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_command(self, test_dir: str, image: str) -> list[str]:
        """Assemble the ``docker run`` command with security flags."""
        return (
            DockerCommand()
            .rm()
            .network("none")
            .read_only()
            .memory(self.memory_limit)
            .cpus(self.cpu_limit)
            .stop_timeout(self.timeout)
            .volume(test_dir, "/workspace", "ro")
            .workdir("/workspace")
            .extra_flags(self.extra_docker_flags)
            .image(image)
            .entrypoint("pytest", "-v", "--tb=short")
            .build()
        )
