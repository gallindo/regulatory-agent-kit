"""Agent tool functions — standalone functions registered to agents by category.

Tool categories:
- READ_ONLY: git_clone, ast_parse, ast_search, es_search (AnalyzerAgent)
- READ_WRITE: git_branch, git_commit, ast_transform, jinja_render (RefactorAgent)
- SANDBOXED: git_read, test_run, jinja_render_test (TestGeneratorAgent)
- EXTERNAL: git_pr_create, notification_send, jinja_render_report (ReporterAgent)
"""

from __future__ import annotations

from typing import Any

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
    # Stub — real implementation will delegate to tools.git module.
    return {"status": "cloned", "repo_url": repo_url, "target_dir": target_dir}


async def ast_parse(file_path: str, language: str = "python") -> dict[str, Any]:
    """Parse a source file into an AST representation.

    Args:
        file_path: Path to the source file to parse.
        language: Programming language of the file.

    Returns:
        A dict with the parsed AST data.
    """
    return {"status": "parsed", "file_path": file_path, "language": language}


async def ast_search(
    root_dir: str,
    pattern: str,
    language: str = "python",
) -> list[dict[str, Any]]:
    """Search for AST patterns across source files.

    Args:
        root_dir: Root directory to search within.
        pattern: The AST pattern or query to match.
        language: Programming language to target.

    Returns:
        A list of match result dicts.
    """
    return [{"root_dir": root_dir, "pattern": pattern, "language": language}]


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
    return [{"index": index, "query": query, "max_results": max_results}]


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
    return {"status": "branched", "repo_dir": repo_dir, "branch_name": branch_name}


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
    return {
        "status": "committed",
        "repo_dir": repo_dir,
        "message": message,
        "file_paths": file_paths or [],
    }


async def ast_transform(
    file_path: str,
    rule_id: str,
    transform_spec: dict[str, Any],
) -> dict[str, Any]:
    """Apply an AST-level transformation to a source file.

    Args:
        file_path: Path to the source file to transform.
        rule_id: The regulation rule driving this transformation.
        transform_spec: Specification of the transformation to apply.

    Returns:
        A dict with transformation status and diff.
    """
    return {
        "status": "transformed",
        "file_path": file_path,
        "rule_id": rule_id,
    }


async def jinja_render(
    template_name: str,
    context: dict[str, Any],
) -> str:
    """Render a Jinja2 template with the given context for code generation.

    Args:
        template_name: Name of the Jinja2 template file.
        context: Template rendering context variables.

    Returns:
        The rendered template string.
    """
    return f"rendered:{template_name}"


# ---------------------------------------------------------------------------
# SANDBOXED tools (TestGeneratorAgent)
# ---------------------------------------------------------------------------


async def git_read(file_path: str) -> str:
    """Read the contents of a file in the repository (read-only).

    Args:
        file_path: Path to the file to read.

    Returns:
        The file contents as a string.
    """
    return f"contents:{file_path}"


async def run_tests(
    test_dir: str,
    test_pattern: str = "test_*.py",
    timeout: int = 300,
) -> dict[str, Any]:
    """Run tests in a sandboxed environment.

    Args:
        test_dir: Directory containing the test files.
        test_pattern: Glob pattern to match test files.
        timeout: Maximum time in seconds for the test run.

    Returns:
        A dict with test execution results.
    """
    return {
        "status": "executed",
        "test_dir": test_dir,
        "test_pattern": test_pattern,
        "passed": 0,
        "failed": 0,
        "total": 0,
    }


async def jinja_render_test(
    template_name: str,
    context: dict[str, Any],
) -> str:
    """Render a Jinja2 template for test file generation (sandboxed).

    Args:
        template_name: Name of the Jinja2 template file.
        context: Template rendering context variables.

    Returns:
        The rendered test file content.
    """
    return f"test_rendered:{template_name}"


# ---------------------------------------------------------------------------
# EXTERNAL tools (ReporterAgent)
# ---------------------------------------------------------------------------


async def git_pr_create(
    repo_dir: str,
    title: str,
    body: str,
    base_branch: str = "main",
    head_branch: str = "",
) -> dict[str, Any]:
    """Create a pull request on the remote repository.

    Args:
        repo_dir: Path to the local repository.
        title: Pull request title.
        body: Pull request body/description.
        base_branch: The branch to merge into.
        head_branch: The branch containing changes.

    Returns:
        A dict with the PR URL and status.
    """
    return {
        "status": "created",
        "title": title,
        "base_branch": base_branch,
        "head_branch": head_branch,
        "pr_url": "",
    }


async def notification_send(
    channel: str,
    message: str,
    severity: str = "info",
) -> dict[str, Any]:
    """Send a notification to the specified channel.

    Args:
        channel: Notification channel identifier.
        message: The notification message body.
        severity: Message severity level (info, warning, error).

    Returns:
        A dict with delivery status.
    """
    return {"status": "sent", "channel": channel, "severity": severity}


async def jinja_render_report(
    template_name: str,
    context: dict[str, Any],
) -> str:
    """Render a Jinja2 template for compliance report generation.

    Args:
        template_name: Name of the Jinja2 template file.
        context: Template rendering context variables.

    Returns:
        The rendered report content.
    """
    return f"report_rendered:{template_name}"


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
