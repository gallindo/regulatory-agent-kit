"""Sandboxed test runner via Docker containers."""

from __future__ import annotations

import ast
import asyncio
import logging
from dataclasses import dataclass, field

from regulatory_agent_kit.exceptions import ToolError

logger = logging.getLogger(__name__)

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
        cmd = [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--read-only",
            f"--memory={_DEFAULT_MEMORY_LIMIT}",
            f"--cpus={_DEFAULT_CPU_LIMIT}",
            f"--stop-timeout={self.timeout}",
            "-v",
            f"{test_dir}:/workspace:ro",
            "-w",
            "/workspace",
            *self.extra_docker_flags,
            image,
            "pytest",
            "-v",
            "--tb=short",
        ]
        return cmd
