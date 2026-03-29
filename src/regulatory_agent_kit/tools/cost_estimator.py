"""LLM cost estimation based on file sizes and model pricing.

Estimates token counts from file content and applies per-model pricing
tables to produce USD cost estimates.  Used by the ``estimate_cost``
activity and the Lite Mode ``CostEstimationPhase``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token estimation heuristics
# ---------------------------------------------------------------------------

# Average characters per token (empirical across Claude / GPT models).
_CHARS_PER_TOKEN = 4

# Overhead tokens per file for system prompt + rule context.
_OVERHEAD_TOKENS_PER_FILE = 500

# Overhead tokens for the per-repo system prompt + plugin context.
_OVERHEAD_TOKENS_PER_REPO = 2000


def estimate_tokens_for_file(content: str) -> int:
    """Estimate the token count for a single file's content.

    Uses the heuristic of ~4 characters per token plus a fixed overhead
    for the system prompt and rule context injected alongside the file.
    """
    content_tokens = len(content) // _CHARS_PER_TOKEN
    return content_tokens + _OVERHEAD_TOKENS_PER_FILE


def estimate_tokens_for_repo(
    repo_path: str | Path,
    file_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """Estimate total tokens for all matching files in a repository.

    Args:
        repo_path: Path to the local repository clone.
        file_patterns: Glob patterns to match (default: common source files).

    Returns:
        Dict with ``total_tokens``, ``file_count``, ``per_file`` breakdown.
    """
    patterns = file_patterns or ["**/*.py", "**/*.java", "**/*.kt", "**/*.js", "**/*.ts"]
    root = Path(repo_path)
    per_file: dict[str, int] = {}
    total_tokens = _OVERHEAD_TOKENS_PER_REPO

    if not root.is_dir():
        return {
            "total_tokens": total_tokens,
            "file_count": 0,
            "per_file": {},
        }

    for pattern in patterns:
        for file_path in root.glob(pattern):
            if file_path.is_file():
                rel = str(file_path.relative_to(root))
                if rel not in per_file:
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        tokens = estimate_tokens_for_file(content)
                        per_file[rel] = tokens
                        total_tokens += tokens
                    except OSError:
                        continue

    return {
        "total_tokens": total_tokens,
        "file_count": len(per_file),
        "per_file": per_file,
    }


# ---------------------------------------------------------------------------
# Model pricing tables (USD per 1M tokens)
# ---------------------------------------------------------------------------

# Pricing as of 2026-03. Kept as a simple dict so it's easy to update.
# Format: {model_prefix: (input_cost_per_1M, output_cost_per_1M)}
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "anthropic/claude-opus": (15.00, 75.00),
    "anthropic/claude-sonnet": (3.00, 15.00),
    "anthropic/claude-haiku": (0.25, 1.25),
    "openai/gpt-4o": (2.50, 10.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4-turbo": (10.00, 30.00),
    "openai/o1": (15.00, 60.00),
    "openai/o1-mini": (1.10, 4.40),
}

# Default fallback when model is not in the table.
_DEFAULT_PRICING: tuple[float, float] = (3.00, 15.00)

# Ratio of output tokens to input tokens (heuristic).
_OUTPUT_RATIO = 0.3


def get_model_pricing(model: str) -> tuple[float, float]:
    """Return (input_cost_per_1M, output_cost_per_1M) for a model.

    Matches on prefix, so ``anthropic/claude-sonnet-4-6`` matches
    ``anthropic/claude-sonnet``.
    """
    for prefix, pricing in MODEL_PRICING.items():
        if model.startswith(prefix):
            return pricing
    return _DEFAULT_PRICING


def estimate_cost_for_tokens(total_tokens: int, model: str) -> float:
    """Estimate USD cost for a given token count and model.

    Splits tokens into input and output using ``_OUTPUT_RATIO`` and
    applies per-model pricing.
    """
    input_cost_per_1m, output_cost_per_1m = get_model_pricing(model)
    input_tokens = int(total_tokens * (1 - _OUTPUT_RATIO))
    output_tokens = total_tokens - input_tokens
    cost = (input_tokens / 1_000_000 * input_cost_per_1m) + (
        output_tokens / 1_000_000 * output_cost_per_1m
    )
    return round(cost, 6)


# ---------------------------------------------------------------------------
# High-level estimator
# ---------------------------------------------------------------------------


class CostEstimator:
    """Estimates LLM cost for a pipeline run across multiple repositories.

    Combines file-level token estimation with model-specific pricing to
    produce the ``CostEstimate`` dict consumed by the pipeline.
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4-6",
        cost_threshold: float = 50.0,
    ) -> None:
        self._model = model
        self._cost_threshold = cost_threshold

    def estimate_for_repos(
        self,
        repo_urls: list[str],
        *,
        repo_paths: dict[str, str] | None = None,
        file_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Estimate cost for a list of repositories.

        When ``repo_paths`` maps URLs to local clone paths, the estimator
        scans file sizes for accurate token counts.  Otherwise it falls
        back to a per-repo heuristic.

        Args:
            repo_urls: List of repository URLs.
            repo_paths: Optional mapping of repo URL → local path.
            file_patterns: Glob patterns for matching source files.

        Returns:
            A dict matching the ``CostEstimate`` model fields.
        """
        paths = repo_paths or {}
        per_repo_cost: dict[str, float] = {}
        total_tokens = 0

        for url in repo_urls:
            local_path = paths.get(url)
            if local_path:
                info = estimate_tokens_for_repo(local_path, file_patterns)
                tokens = info["total_tokens"]
            else:
                tokens = _estimate_tokens_heuristic()
            total_tokens += tokens
            per_repo_cost[url] = estimate_cost_for_tokens(tokens, self._model)

        total_cost = sum(per_repo_cost.values())
        exceeds = total_cost > self._cost_threshold

        return {
            "estimated_total_cost": round(total_cost, 4),
            "per_repo_cost": per_repo_cost,
            "estimated_total_tokens": total_tokens,
            "model_used": self._model,
            "exceeds_threshold": exceeds,
        }


def _estimate_tokens_heuristic() -> int:
    """Fallback token estimate when a repo is not cloned locally.

    Assumes a medium-sized service with ~50 source files averaging 200
    lines (~800 chars) each.
    """
    avg_files = 50
    avg_chars = 800
    return (
        _OVERHEAD_TOKENS_PER_REPO
        + avg_files * (avg_chars // _CHARS_PER_TOKEN + _OVERHEAD_TOKENS_PER_FILE)
    )
