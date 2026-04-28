"""Tests for TestRunner — sandboxed execution with static analysis gate."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from unittest.mock import AsyncMock, patch

import pytest

from regulatory_agent_kit.tools.test_runner import (
    TestRunner,
    ValidationResult,
    _check_dangerous_imports,
    validate_test_files,
)

# ======================================================================
# _check_dangerous_imports
# ======================================================================


class TestCheckDangerousImports:
    """Test static analysis for dangerous imports."""

    def test_rejects_import_os(self) -> None:
        violations = _check_dangerous_imports("import os\npath = os.getcwd()")
        assert "os" in violations

    def test_rejects_import_subprocess(self) -> None:
        violations = _check_dangerous_imports("import subprocess")
        assert "subprocess" in violations

    def test_rejects_import_socket(self) -> None:
        violations = _check_dangerous_imports("import socket")
        assert "socket" in violations

    def test_rejects_import_shutil(self) -> None:
        violations = _check_dangerous_imports("import shutil")
        assert "shutil" in violations

    def test_rejects_import_ctypes(self) -> None:
        violations = _check_dangerous_imports("import ctypes")
        assert "ctypes" in violations

    def test_rejects_import_signal(self) -> None:
        violations = _check_dangerous_imports("import signal")
        assert "signal" in violations

    def test_rejects_from_os_import(self) -> None:
        violations = _check_dangerous_imports("from os.path import join")
        assert "os" in violations

    def test_accepts_safe_imports(self) -> None:
        source = "import json\nimport math\nfrom pathlib import Path"
        violations = _check_dangerous_imports(source)
        assert violations == []

    def test_handles_syntax_error(self) -> None:
        violations = _check_dangerous_imports("def broken(:")
        assert violations == []

    def test_rejects_multiple_dangerous(self) -> None:
        violations = _check_dangerous_imports("import os\nimport subprocess")
        assert "os" in violations
        assert "subprocess" in violations


# ======================================================================
# validate_test_files
# ======================================================================


class TestValidateTestFiles:
    """Test directory-level static analysis."""

    def test_safe_directory(self, tmp_path: Path) -> None:
        (tmp_path / "test_safe.py").write_text("import json\ndef test_ok(): pass\n")
        result = validate_test_files(tmp_path)
        assert result.safe is True
        assert result.files_scanned == 1
        assert result.violations == []

    def test_dangerous_directory(self, tmp_path: Path) -> None:
        (tmp_path / "test_bad.py").write_text("import os\ndef test_bad(): pass\n")
        result = validate_test_files(tmp_path)
        assert result.safe is False
        assert len(result.violations) == 1
        assert "os" in result.violations[0]

    def test_mixed_directory(self, tmp_path: Path) -> None:
        (tmp_path / "test_safe.py").write_text("import json\n")
        (tmp_path / "test_bad.py").write_text("import subprocess\n")
        result = validate_test_files(tmp_path)
        assert result.safe is False
        assert result.files_scanned == 2
        assert len(result.violations) == 1

    def test_nested_directory(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "test_nested.py").write_text("import socket\n")
        result = validate_test_files(tmp_path)
        assert result.safe is False
        assert "socket" in result.violations[0]

    def test_nonexistent_directory(self) -> None:
        result = validate_test_files("/nonexistent/path")
        assert result.safe is True
        assert result.files_scanned == 0

    def test_empty_directory(self, tmp_path: Path) -> None:
        result = validate_test_files(tmp_path)
        assert result.safe is True
        assert result.files_scanned == 0

    def test_ignores_non_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "readme.md").write_text("import os\n")
        (tmp_path / "config.yaml").write_text("import subprocess\n")
        result = validate_test_files(tmp_path)
        assert result.safe is True
        assert result.files_scanned == 0

    def test_validation_result_is_frozen(self) -> None:
        result = ValidationResult(safe=True, violations=[], files_scanned=0)
        with pytest.raises(AttributeError):
            result.safe = False  # type: ignore[misc]


# ======================================================================
# TestRunner Docker command building
# ======================================================================


class TestTestRunnerCommand:
    """Test Docker command construction with security flags."""

    def test_build_command_includes_security_flags(self) -> None:
        runner = TestRunner()
        cmd = runner._build_command("/tests", "python:3.12-slim")
        assert "--network=none" in cmd
        assert "--read-only" in cmd
        assert "--memory=512m" in cmd
        assert "--cpus=1" in cmd

    def test_build_command_includes_volume_mount(self) -> None:
        runner = TestRunner()
        cmd = runner._build_command("/my/tests", "python:3.12-slim")
        assert "/my/tests:/workspace:ro" in " ".join(cmd)

    def test_build_command_uses_custom_image(self) -> None:
        runner = TestRunner()
        cmd = runner._build_command("/tests", "custom-image:latest")
        assert "custom-image:latest" in cmd

    def test_build_command_includes_pytest(self) -> None:
        runner = TestRunner()
        cmd = runner._build_command("/tests", "python:3.12-slim")
        assert "pytest" in cmd

    def test_extra_docker_flags(self) -> None:
        runner = TestRunner(extra_docker_flags=["--cap-drop=ALL"])
        cmd = runner._build_command("/tests", "python:3.12-slim")
        assert "--cap-drop=ALL" in cmd

    def test_custom_memory_and_cpu(self) -> None:
        runner = TestRunner(memory_limit="1g", cpu_limit="2")
        cmd = runner._build_command("/tests", "python:3.12-slim")
        assert "--memory=1g" in cmd
        assert "--cpus=2" in cmd


# ======================================================================
# TestRunner.run_tests — pre-flight validation
# ======================================================================


class TestRunTestsValidation:
    """Test that run_tests blocks dangerous test files."""

    async def test_blocks_dangerous_tests(self, tmp_path: Path) -> None:
        # Write a test file that imports a dangerous module
        (tmp_path / "test_evil.py").write_text("import os\n")
        runner = TestRunner()
        result = await runner.run_tests(str(tmp_path))

        assert result.passed is False
        assert result.returncode == -2
        assert "BLOCKED" in result.stderr
        assert result.validation is not None
        assert result.validation.safe is False

    async def test_passes_safe_tests_to_docker(self, tmp_path: Path) -> None:
        (tmp_path / "test_ok.py").write_text("def test_one(): assert True\n")

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"1 passed", b""))
        mock_proc.returncode = 0
        mock_proc.kill = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            runner = TestRunner()
            result = await runner.run_tests(str(tmp_path))

        assert result.passed is True
        assert result.validation is not None
        assert result.validation.safe is True

    async def test_skip_validation_flag(self, tmp_path: Path) -> None:
        (tmp_path / "test_evil.py").write_text("import os\n")

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"1 passed", b""))
        mock_proc.returncode = 0
        mock_proc.kill = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            runner = TestRunner(skip_validation=True)
            result = await runner.run_tests(str(tmp_path))

        # Validation skipped — proceeds to Docker
        assert result.passed is True
        assert result.validation is None

    async def test_validation_result_attached_to_output(self, tmp_path: Path) -> None:
        (tmp_path / "test_safe.py").write_text("def test_x(): pass\n")

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))
        mock_proc.returncode = 0
        mock_proc.kill = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            runner = TestRunner()
            result = await runner.run_tests(str(tmp_path))

        assert result.validation is not None
        assert result.validation.files_scanned == 1
