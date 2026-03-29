"""Agent tool functions — standalone functions registered to agents by category.

Each tool delegates to a real service implementation from the ``tools``
package.  Errors are caught and returned as structured error dicts so the
LLM agent receives actionable feedback rather than unhandled exceptions.

Tool categories:
- READ_ONLY: git_clone, ast_parse, ast_search, es_search (AnalyzerAgent)
- READ_WRITE: git_branch, git_commit, ast_transform, jinja_render (RefactorAgent)
- SANDBOXED: git_read, test_run, jinja_render_test (TestGeneratorAgent)
- EXTERNAL: git_pr_create, notification_send, jinja_render_report (ReporterAgent)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# READ-ONLY tools (AnalyzerAgent)
# ---------------------------------------------------------------------------


async def git_clone(repo_url: str, target_dir: str) -> dict[str, Any]:
    """Clone a git repository to a local directory for analysis.

    Args:
        repo_url: The URL of the git repository to clone.
        target_dir: The local directory path to clone into.

    Returns:
        A dict with clone status and path information.
    """
    from regulatory_agent_kit.tools.git_client import GitClient

    client = GitClient()
    try:
        result = await client.clone(repo_url, target_dir)
        return {
            "status": "cloned",
            "repo_url": repo_url,
            "target_dir": target_dir,
            "stdout": result.stdout,
        }
    except Exception as exc:
        logger.warning("git_clone failed for %s: %s", repo_url, exc)
        return {"status": "error", "repo_url": repo_url, "error": str(exc)}


async def ast_parse(file_path: str, language: str = "") -> dict[str, Any]:
    """Parse a source file into an AST representation.

    Args:
        file_path: Path to the source file to parse.
        language: Programming language of the file (auto-detected if empty).

    Returns:
        A dict with parsed AST summary data.
    """
    from regulatory_agent_kit.tools.ast_engine import ASTEngine, _detect_language

    engine = ASTEngine()
    try:
        resolved_lang = language or _detect_language(file_path)
        source = Path(file_path).read_text(encoding="utf-8")
        tree = engine.parse(source, resolved_lang)
        classes = engine.find_classes(tree)
        methods = engine.find_methods(tree)
        annotations = engine.find_annotations(tree)
        return {
            "status": "parsed",
            "file_path": file_path,
            "language": resolved_lang,
            "classes": len(classes),
            "methods": len(methods),
            "annotations": len(annotations),
            "root_node_type": tree.root_node.type if tree else "",
        }
    except Exception as exc:
        logger.warning("ast_parse failed for %s: %s", file_path, exc)
        return {
            "status": "error",
            "file_path": file_path,
            "language": language,
            "error": str(exc),
        }


async def ast_search(
    root_dir: str,
    pattern: str,
    language: str = "python",
) -> list[dict[str, Any]]:
    """Search for AST patterns across source files.

    Scans files matching the language extension in *root_dir*, parses each,
    and checks whether any class implements the interface named in *pattern*.

    Args:
        root_dir: Root directory to search within.
        pattern: Interface or class name to search for (e.g. ``ICTService``).
        language: Programming language to target.

    Returns:
        A list of match result dicts with file path and match details.
    """
    from regulatory_agent_kit.tools.ast_engine import (
        _EXTENSION_MAP,
        ASTEngine,
    )

    engine = ASTEngine()
    results: list[dict[str, Any]] = []

    # Find the file extension for the target language
    ext = next((e for e, lang in _EXTENSION_MAP.items() if lang == language), None)
    if ext is None:
        return [{"error": f"Unsupported language: {language}"}]

    root = Path(root_dir)
    if not root.is_dir():
        return [{"error": f"Directory not found: {root_dir}"}]

    for file_path in root.rglob(f"*{ext}"):
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = engine.parse(source, language)
            if engine.check_implements(tree, pattern):
                results.append({
                    "file_path": str(file_path),
                    "pattern": pattern,
                    "match": True,
                    "language": language,
                })
        except Exception:  # noqa: S112
            continue

    return results


async def es_search(
    index: str,
    query: str,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Search the Elasticsearch regulatory knowledge base.

    Args:
        index: Elasticsearch index to query.
        query: The search query string.
        max_results: Maximum number of results to return.

    Returns:
        A list of matching documents.
    """
    from regulatory_agent_kit.tools.search_client import SearchClient

    client = SearchClient()
    try:
        if "context" in index:
            return await client.search_context(query, limit=max_results)
        return await client.search_rules(query)
    except Exception as exc:
        logger.warning("es_search failed: %s", exc)
        return [{"error": str(exc)}]
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# READ-WRITE tools (RefactorAgent)
# ---------------------------------------------------------------------------


async def git_branch(repo_dir: str, branch_name: str) -> dict[str, Any]:
    """Create and checkout a new git branch for remediation changes.

    Args:
        repo_dir: Path to the local repository.
        branch_name: Name of the branch to create.

    Returns:
        A dict with branch creation status.
    """
    from regulatory_agent_kit.tools.git_client import GitClient

    client = GitClient()
    try:
        result = await client.create_branch(repo_dir, branch_name)
        return {
            "status": "branched",
            "repo_dir": repo_dir,
            "branch_name": branch_name,
            "stdout": result.stdout,
        }
    except Exception as exc:
        logger.warning("git_branch failed: %s", exc)
        return {"status": "error", "branch_name": branch_name, "error": str(exc)}


async def git_commit(
    repo_dir: str,
    message: str,
    file_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Stage and commit changes in the repository.

    Args:
        repo_dir: Path to the local repository.
        message: Commit message.
        file_paths: Specific file paths to stage; stages all if None.

    Returns:
        A dict with commit SHA and status.
    """
    from regulatory_agent_kit.tools.git_client import GitClient

    client = GitClient()
    try:
        files = file_paths or ["."]
        await client.add(repo_dir, files)
        result = await client.commit(repo_dir, message)
        return {
            "status": "committed",
            "repo_dir": repo_dir,
            "message": message,
            "stdout": result.stdout,
        }
    except Exception as exc:
        logger.warning("git_commit failed: %s", exc)
        return {"status": "error", "message": message, "error": str(exc)}


async def ast_transform(
    file_path: str,
    rule_id: str,
    transform_spec: dict[str, Any],
) -> dict[str, Any]:
    """Apply an AST-level transformation to a source file.

    Reads the file, applies the transformation spec (insert, replace, or
    append), and writes the result back.

    Args:
        file_path: Path to the source file to transform.
        rule_id: The regulation rule driving this transformation.
        transform_spec: Specification with ``action`` (insert/replace/append),
            ``content`` (text to insert), and optional ``line`` (target line).

    Returns:
        A dict with transformation status and diff.
    """
    path = Path(file_path)
    try:
        if not path.exists():
            return {"status": "error", "file_path": file_path, "error": "File not found"}

        original = path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)

        action = transform_spec.get("action", "append")
        content = transform_spec.get("content", "")
        target_line = transform_spec.get("line", len(lines))

        if action == "insert":
            lines.insert(min(target_line, len(lines)), content + "\n")
        elif action == "replace" and target_line < len(lines):
            lines[target_line] = content + "\n"
        else:  # append
            lines.append(content + "\n")

        modified = "".join(lines)
        path.write_text(modified, encoding="utf-8")

        return {
            "status": "transformed",
            "file_path": file_path,
            "rule_id": rule_id,
            "action": action,
            "lines_before": len(original.splitlines()),
            "lines_after": len(modified.splitlines()),
        }
    except Exception as exc:
        logger.warning("ast_transform failed for %s: %s", file_path, exc)
        return {"status": "error", "file_path": file_path, "rule_id": rule_id, "error": str(exc)}


async def jinja_render(
    template_name: str,
    context: dict[str, Any],
) -> str:
    """Render a Jinja2 template with the given context for code generation.

    Args:
        template_name: Path to the Jinja2 template file.
        context: Template rendering context variables.

    Returns:
        The rendered template string, or an error message.
    """
    from regulatory_agent_kit.templates.engine import TemplateEngine

    engine = TemplateEngine()
    try:
        return engine.render(Path(template_name), context)
    except Exception as exc:
        logger.warning("jinja_render failed for %s: %s", template_name, exc)
        return f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# SANDBOXED tools (TestGeneratorAgent)
# ---------------------------------------------------------------------------


async def git_read(file_path: str) -> str:
    """Read the contents of a file in the repository (read-only).

    Args:
        file_path: Path to the file to read.

    Returns:
        The file contents as a string, or an error message.
    """
    path = Path(file_path)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"ERROR: File not found: {file_path}"
    except Exception as exc:
        return f"ERROR: {exc}"


async def run_tests(
    test_dir: str,
    test_pattern: str = "test_*.py",
    timeout: int = 300,
) -> dict[str, Any]:
    """Run tests in a sandboxed Docker container.

    Args:
        test_dir: Directory containing the test files.
        test_pattern: Glob pattern to match test files (informational).
        timeout: Maximum time in seconds for the test run.

    Returns:
        A dict with test execution results.
    """
    from regulatory_agent_kit.tools.test_runner import TestRunner

    runner = TestRunner(timeout=timeout)
    try:
        result = await runner.run_tests(test_dir, timeout=timeout)
        return {
            "status": "executed",
            "test_dir": test_dir,
            "passed": result.passed,
            "returncode": result.returncode,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:2000],
            "timed_out": result.timed_out,
        }
    except Exception as exc:
        logger.warning("run_tests failed: %s", exc)
        return {
            "status": "error",
            "test_dir": test_dir,
            "error": str(exc),
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
        }


async def jinja_render_test(
    template_name: str,
    context: dict[str, Any],
) -> str:
    """Render a Jinja2 template for test file generation (sandboxed).

    Args:
        template_name: Path to the Jinja2 template file.
        context: Template rendering context variables.

    Returns:
        The rendered test file content, or an error message.
    """
    from regulatory_agent_kit.templates.engine import TemplateEngine

    engine = TemplateEngine()
    try:
        return engine.render(Path(template_name), context)
    except Exception as exc:
        logger.warning("jinja_render_test failed for %s: %s", template_name, exc)
        return f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# EXTERNAL tools (ReporterAgent)
# ---------------------------------------------------------------------------


async def git_pr_create(
    repo_url: str,
    title: str,
    body: str,
    base_branch: str = "main",
    head_branch: str = "",
) -> dict[str, Any]:
    """Create a pull request on the remote repository.

    Args:
        repo_url: Repository URL (used to determine the git provider).
        title: Pull request title.
        body: Pull request body/description.
        base_branch: The branch to merge into.
        head_branch: The branch containing changes.

    Returns:
        A dict with the PR URL and status.
    """
    from regulatory_agent_kit.tools.git_provider import create_git_provider

    try:
        provider = create_git_provider(repo_url)
        result = await provider.create_pull_request(
            title=title,
            body=body,
            head=head_branch,
            base=base_branch,
        )
        return {
            "status": "created",
            "title": title,
            "pr_url": result.get("html_url", result.get("web_url", "")),
            "pr_number": result.get("number", result.get("iid", 0)),
        }
    except Exception as exc:
        logger.warning("git_pr_create failed: %s", exc)
        return {
            "status": "error",
            "title": title,
            "error": str(exc),
            "pr_url": "",
        }


async def notification_send(
    channel: str,
    message: str,
    severity: str = "info",
) -> dict[str, Any]:
    """Send a notification to the specified channel.

    Args:
        channel: Notification channel identifier (slack, email, webhook).
        message: The notification message body.
        severity: Message severity level (info, warning, error).

    Returns:
        A dict with delivery status.
    """
    from regulatory_agent_kit.tools.notification import create_notifier

    try:
        notifier = create_notifier(channel)
        if severity == "error":
            await notifier.send_error(run_id="", error=message)
        else:
            await notifier.send_pipeline_complete(run_id="", summary=message)
        return {"status": "sent", "channel": channel, "severity": severity}
    except Exception as exc:
        logger.warning("notification_send failed: %s", exc)
        return {"status": "error", "channel": channel, "error": str(exc)}


async def jinja_render_report(
    template_name: str,
    context: dict[str, Any],
) -> str:
    """Render a Jinja2 template for compliance report generation.

    Args:
        template_name: Path to the Jinja2 template file.
        context: Template rendering context variables.

    Returns:
        The rendered report content, or an error message.
    """
    from regulatory_agent_kit.templates.engine import TemplateEngine

    engine = TemplateEngine()
    try:
        return engine.render(Path(template_name), context)
    except Exception as exc:
        logger.warning("jinja_render_report failed for %s: %s", template_name, exc)
        return f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# Tool groupings for agent registration
# ---------------------------------------------------------------------------

ANALYZER_TOOLS: list[object] = [git_clone, ast_parse, ast_search, es_search]
"""Read-only tools for the AnalyzerAgent."""

REFACTOR_TOOLS: list[object] = [git_branch, git_commit, ast_transform, jinja_render]
"""Read-write tools for the RefactorAgent."""

TEST_GENERATOR_TOOLS: list[object] = [git_read, run_tests, jinja_render_test]
"""Sandboxed tools for the TestGeneratorAgent."""

REPORTER_TOOLS: list[object] = [
    git_pr_create,
    notification_send,
    jinja_render_report,
]
"""External tools for the ReporterAgent."""
