"""Tests for TestRunner (Phase 7)."""

from __future__ import annotations

from regulatory_agent_kit.tools.test_runner import TestRunner, _check_dangerous_imports


# ======================================================================
# _check_dangerous_imports
# ======================================================================


class TestCheckDangerousImports:
    """Test static analysis for dangerous imports."""

    def test_rejects_import_os(self) -> None:
        source = "import os\npath = os.getcwd()"
        violations = _check_dangerous_imports(source)
        assert "os" in violations

    def test_rejects_import_subprocess(self) -> None:
        source = "import subprocess\nresult = subprocess.run(['ls'])"
        violations = _check_dangerous_imports(source)
        assert "subprocess" in violations

    def test_rejects_import_socket(self) -> None:
        source = "import socket\ns = socket.socket()"
        violations = _check_dangerous_imports(source)
        assert "socket" in violations

    def test_rejects_from_os_import(self) -> None:
        source = "from os.path import join"
        violations = _check_dangerous_imports(source)
        assert "os" in violations

    def test_accepts_safe_imports(self) -> None:
        source = "import json\nimport math\nfrom pathlib import Path"
        violations = _check_dangerous_imports(source)
        assert violations == []

    def test_handles_syntax_error(self) -> None:
        source = "def broken(:"
        violations = _check_dangerous_imports(source)
        assert violations == []

    def test_rejects_multiple_dangerous(self) -> None:
        source = "import os\nimport subprocess"
        violations = _check_dangerous_imports(source)
        assert "os" in violations
        assert "subprocess" in violations


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
