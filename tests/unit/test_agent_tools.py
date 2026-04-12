"""Tests for agent tool implementations — verify delegation to real services."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from unittest.mock import AsyncMock, MagicMock, patch

from regulatory_agent_kit.agents.tools import (
    ast_parse,
    ast_search,
    ast_transform,
    es_search,
    git_branch,
    git_clone,
    git_commit,
    git_pr_create,
    git_read,
    jinja_render,
    jinja_render_report,
    jinja_render_test,
    notification_send,
    run_tests,
)

# Patch targets point to the source module, not agents.tools, because
# the tools use local imports inside function bodies.
_GIT_CLIENT = "regulatory_agent_kit.tools.git_client.GitClient"
_AST_ENGINE = "regulatory_agent_kit.tools.ast_engine.ASTEngine"
_SEARCH_CLIENT = "regulatory_agent_kit.tools.search_client.SearchClient"
_TEST_RUNNER = "regulatory_agent_kit.tools.test_runner.TestRunner"
_GIT_PROVIDER = "regulatory_agent_kit.tools.git_provider.create_git_provider"
_NOTIFIER = "regulatory_agent_kit.tools.notification.create_notifier"


# ------------------------------------------------------------------
# git_clone
# ------------------------------------------------------------------


class TestGitClone:
    async def test_delegates_to_git_client(self) -> None:
        mock_result = MagicMock(stdout="Cloning into 'repo'...")
        mock_client = AsyncMock()
        mock_client.clone = AsyncMock(return_value=mock_result)

        with patch(_GIT_CLIENT, return_value=mock_client):
            result = await git_clone("https://github.com/org/repo", "/tmp/repo")  # noqa: S108

        assert result["status"] == "cloned"
        assert result["repo_url"] == "https://github.com/org/repo"
        mock_client.clone.assert_awaited_once()

    async def test_returns_error_on_failure(self) -> None:
        mock_client = AsyncMock()
        mock_client.clone = AsyncMock(side_effect=RuntimeError("clone failed"))

        with patch(_GIT_CLIENT, return_value=mock_client):
            result = await git_clone("https://bad-url", "/tmp/repo")  # noqa: S108

        assert result["status"] == "error"
        assert "clone failed" in result["error"]


# ------------------------------------------------------------------
# ast_parse
# ------------------------------------------------------------------


class TestAstParse:
    async def test_parses_file(self, tmp_path: Path) -> None:
        py_file = tmp_path / "test.py"
        py_file.write_text("class Foo:\n    pass\n")

        mock_tree = MagicMock()
        mock_tree.root_node.type = "module"
        mock_engine = MagicMock()
        mock_engine.parse.return_value = mock_tree
        mock_engine.find_classes.return_value = [MagicMock()]
        mock_engine.find_methods.return_value = []
        mock_engine.find_annotations.return_value = []

        with patch(_AST_ENGINE, return_value=mock_engine):
            result = await ast_parse(str(py_file), "python")

        assert result["status"] == "parsed"
        assert result["classes"] == 1

    async def test_returns_error_for_missing_file(self) -> None:
        result = await ast_parse("/nonexistent/file.py", "python")
        assert result["status"] == "error"


# ------------------------------------------------------------------
# ast_search
# ------------------------------------------------------------------


class TestAstSearch:
    async def test_returns_empty_for_bad_dir(self) -> None:
        results = await ast_search("/nonexistent", "FooInterface", "python")
        assert len(results) == 1
        assert "error" in results[0]

    async def test_returns_empty_for_bad_language(self) -> None:
        results = await ast_search("/tmp", "Foo", "brainfuck")  # noqa: S108
        assert len(results) == 1
        assert "Unsupported" in results[0]["error"]


# ------------------------------------------------------------------
# es_search
# ------------------------------------------------------------------


class TestEsSearch:
    async def test_delegates_to_search_client(self) -> None:
        mock_client = AsyncMock()
        mock_client.search_rules = AsyncMock(return_value=[{"rule_id": "R-1"}])
        mock_client.close = AsyncMock()

        with patch(_SEARCH_CLIENT, return_value=mock_client):
            results = await es_search("rak-regulations", "audit logging")

        assert len(results) == 1
        assert results[0]["rule_id"] == "R-1"

    async def test_context_search(self) -> None:
        mock_client = AsyncMock()
        mock_client.search_context = AsyncMock(return_value=[{"content": "text"}])
        mock_client.close = AsyncMock()

        with patch(_SEARCH_CLIENT, return_value=mock_client):
            await es_search("rak-regulation-context", "Example", max_results=5)

        mock_client.search_context.assert_awaited_once_with("Example", limit=5)


# ------------------------------------------------------------------
# git_branch
# ------------------------------------------------------------------


class TestGitBranch:
    async def test_delegates_to_git_client(self) -> None:
        mock_result = MagicMock(stdout="Switched to a new branch")
        mock_client = AsyncMock()
        mock_client.create_branch = AsyncMock(return_value=mock_result)

        with patch(_GIT_CLIENT, return_value=mock_client):
            result = await git_branch("/repo", "rak/fix")

        assert result["status"] == "branched"
        mock_client.create_branch.assert_awaited_once()


# ------------------------------------------------------------------
# git_commit
# ------------------------------------------------------------------


class TestGitCommit:
    async def test_stages_and_commits(self) -> None:
        mock_result = MagicMock(stdout="[rak/fix abc123] commit msg")
        mock_client = AsyncMock()
        mock_client.add = AsyncMock(return_value=mock_result)
        mock_client.commit = AsyncMock(return_value=mock_result)

        with patch(_GIT_CLIENT, return_value=mock_client):
            result = await git_commit("/repo", "fix: compliance", ["file.py"])

        assert result["status"] == "committed"
        mock_client.add.assert_awaited_once()
        mock_client.commit.assert_awaited_once()


# ------------------------------------------------------------------
# ast_transform
# ------------------------------------------------------------------


class TestAstTransform:
    async def test_appends_content(self, tmp_path: Path) -> None:
        f = tmp_path / "file.py"
        f.write_text("line1\nline2\n")

        result = await ast_transform(
            str(f), "R-001", {"action": "append", "content": "# added"}
        )
        assert result["status"] == "transformed"
        assert "# added" in f.read_text()

    async def test_inserts_content_at_line(self, tmp_path: Path) -> None:
        f = tmp_path / "file.py"
        f.write_text("line1\nline2\n")

        result = await ast_transform(
            str(f), "R-001", {"action": "insert", "content": "# inserted", "line": 1}
        )
        assert result["status"] == "transformed"
        lines = f.read_text().splitlines()
        assert lines[1] == "# inserted"

    async def test_returns_error_for_missing_file(self) -> None:
        result = await ast_transform(
            "/no/file.py", "R-001", {"action": "append", "content": ""}
        )
        assert result["status"] == "error"


# ------------------------------------------------------------------
# jinja_render
# ------------------------------------------------------------------


class TestJinjaRender:
    async def test_renders_template(self, tmp_path: Path) -> None:
        tmpl = tmp_path / "test.j2"
        tmpl.write_text("Hello {{ name }}!")
        result = await jinja_render(str(tmpl), {"name": "World"})
        assert result == "Hello World!"

    async def test_returns_error_for_missing_template(self) -> None:
        result = await jinja_render("/no/template.j2", {})
        assert result.startswith("ERROR:")


# ------------------------------------------------------------------
# git_read
# ------------------------------------------------------------------


class TestGitRead:
    async def test_reads_file(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hello")
        result = await git_read(str(f))
        assert result == "hello"

    async def test_returns_error_for_missing_file(self) -> None:
        result = await git_read("/no/file.txt")
        assert "ERROR" in result


# ------------------------------------------------------------------
# run_tests
# ------------------------------------------------------------------


class TestRunTests:
    async def test_delegates_to_test_runner(self) -> None:
        mock_result = MagicMock(
            passed=True, returncode=0, stdout="1 passed", stderr="", timed_out=False
        )
        mock_runner = AsyncMock()
        mock_runner.run_tests = AsyncMock(return_value=mock_result)

        with patch(_TEST_RUNNER, return_value=mock_runner):
            result = await run_tests("/tests", timeout=60)

        assert result["status"] == "executed"
        assert result["passed"] is True

    async def test_returns_error_when_docker_missing(self) -> None:
        mock_runner = AsyncMock()
        mock_runner.run_tests = AsyncMock(side_effect=RuntimeError("docker not found"))

        with patch(_TEST_RUNNER, return_value=mock_runner):
            result = await run_tests("/tests")

        assert result["status"] == "error"


# ------------------------------------------------------------------
# jinja_render_test / jinja_render_report
# ------------------------------------------------------------------


class TestJinjaRenderVariants:
    async def test_render_test(self, tmp_path: Path) -> None:
        tmpl = tmp_path / "test.j2"
        tmpl.write_text("def test_{{ name }}(): pass")
        result = await jinja_render_test(str(tmpl), {"name": "foo"})
        assert result == "def test_foo(): pass"

    async def test_render_report(self, tmp_path: Path) -> None:
        tmpl = tmp_path / "report.j2"
        tmpl.write_text("Report for {{ run_id }}")
        result = await jinja_render_report(str(tmpl), {"run_id": "abc"})
        assert result == "Report for abc"


# ------------------------------------------------------------------
# git_pr_create
# ------------------------------------------------------------------


class TestGitPrCreate:
    async def test_delegates_to_git_provider(self) -> None:
        mock_provider = AsyncMock()
        mock_provider.create_pull_request = AsyncMock(
            return_value={"html_url": "https://github.com/org/repo/pull/1", "number": 1}
        )

        with patch(_GIT_PROVIDER, return_value=mock_provider):
            result = await git_pr_create(
                "https://github.com/org/repo",
                "Fix compliance",
                "Body text",
                head_branch="rak/fix",
            )

        assert result["status"] == "created"
        assert "pull/1" in result["pr_url"]

    async def test_returns_error_on_failure(self) -> None:
        with patch(_GIT_PROVIDER, side_effect=RuntimeError("bad URL")):
            result = await git_pr_create("bad://url", "Title", "Body")

        assert result["status"] == "error"


# ------------------------------------------------------------------
# notification_send
# ------------------------------------------------------------------


class TestNotificationSend:
    async def test_sends_via_notifier(self) -> None:
        mock_notifier = AsyncMock()
        mock_notifier.send_pipeline_complete = AsyncMock()

        with patch(_NOTIFIER, return_value=mock_notifier):
            result = await notification_send("webhook", "Pipeline done", "info")

        assert result["status"] == "sent"
        mock_notifier.send_pipeline_complete.assert_awaited_once()

    async def test_sends_error_severity(self) -> None:
        mock_notifier = AsyncMock()
        mock_notifier.send_error = AsyncMock()

        with patch(_NOTIFIER, return_value=mock_notifier):
            result = await notification_send("webhook", "Failed!", "error")

        assert result["status"] == "sent"
        mock_notifier.send_error.assert_awaited_once()
