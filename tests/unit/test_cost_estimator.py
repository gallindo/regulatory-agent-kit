"""Tests for the cost estimation service."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from regulatory_agent_kit.tools.cost_estimator import (
    CostEstimator,
    estimate_cost_for_tokens,
    estimate_tokens_for_file,
    estimate_tokens_for_repo,
    get_model_pricing,
)

# ------------------------------------------------------------------
# Token estimation
# ------------------------------------------------------------------


class TestTokenEstimation:
    def test_empty_file_returns_overhead(self) -> None:
        tokens = estimate_tokens_for_file("")
        assert tokens == 500  # _OVERHEAD_TOKENS_PER_FILE

    def test_token_count_scales_with_content(self) -> None:
        short = estimate_tokens_for_file("x" * 100)
        long = estimate_tokens_for_file("x" * 10000)
        assert long > short

    def test_token_count_is_deterministic(self) -> None:
        content = "def foo(): pass\n" * 100
        assert estimate_tokens_for_file(content) == estimate_tokens_for_file(content)

    def test_repo_estimation_with_real_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("class Foo:\n    pass\n")
        (tmp_path / "util.py").write_text("def helper(): return 1\n")
        result = estimate_tokens_for_repo(tmp_path, ["**/*.py"])
        assert result["file_count"] == 2
        assert result["total_tokens"] > 2000  # overhead + file tokens
        assert "main.py" in result["per_file"]

    def test_repo_estimation_nonexistent_dir(self) -> None:
        result = estimate_tokens_for_repo("/nonexistent/path")
        assert result["file_count"] == 0
        assert result["total_tokens"] == 2000  # just repo overhead

    def test_repo_estimation_empty_dir(self, tmp_path: Path) -> None:
        result = estimate_tokens_for_repo(tmp_path)
        assert result["file_count"] == 0

    def test_repo_estimation_ignores_non_matching_files(self, tmp_path: Path) -> None:
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "main.py").write_text("x = 1\n")
        result = estimate_tokens_for_repo(tmp_path, ["**/*.py"])
        assert result["file_count"] == 1


# ------------------------------------------------------------------
# Model pricing
# ------------------------------------------------------------------


class TestModelPricing:
    def test_claude_sonnet_pricing(self) -> None:
        inp, out = get_model_pricing("anthropic/claude-sonnet-4-6")
        assert inp == 3.0
        assert out == 15.0

    def test_claude_opus_pricing(self) -> None:
        inp, out = get_model_pricing("anthropic/claude-opus-4-6")
        assert inp == 15.0
        assert out == 75.0

    def test_gpt4o_pricing(self) -> None:
        inp, out = get_model_pricing("openai/gpt-4o")
        assert inp == 2.5
        assert out == 10.0

    def test_unknown_model_uses_default(self) -> None:
        inp, out = get_model_pricing("unknown/model-v1")
        assert inp == 3.0  # default
        assert out == 15.0

    def test_prefix_matching(self) -> None:
        # "anthropic/claude-haiku-4-5" should match "anthropic/claude-haiku"
        inp, _out = get_model_pricing("anthropic/claude-haiku-4-5")
        assert inp == 0.25


# ------------------------------------------------------------------
# Cost calculation
# ------------------------------------------------------------------


class TestCostCalculation:
    def test_zero_tokens_returns_zero(self) -> None:
        cost = estimate_cost_for_tokens(0, "anthropic/claude-sonnet-4-6")
        assert cost == 0.0

    def test_cost_scales_with_tokens(self) -> None:
        small = estimate_cost_for_tokens(1000, "anthropic/claude-sonnet-4-6")
        large = estimate_cost_for_tokens(1_000_000, "anthropic/claude-sonnet-4-6")
        assert large > small

    def test_expensive_model_costs_more(self) -> None:
        cheap = estimate_cost_for_tokens(100_000, "anthropic/claude-haiku-4-5")
        expensive = estimate_cost_for_tokens(100_000, "anthropic/claude-opus-4-6")
        assert expensive > cheap

    def test_cost_is_positive(self) -> None:
        cost = estimate_cost_for_tokens(50_000, "openai/gpt-4o")
        assert cost > 0


# ------------------------------------------------------------------
# CostEstimator
# ------------------------------------------------------------------


class TestCostEstimator:
    def test_estimate_for_repos_heuristic(self) -> None:
        estimator = CostEstimator(
            model="anthropic/claude-sonnet-4-6", cost_threshold=50.0
        )
        result = estimator.estimate_for_repos([
            "https://github.com/org/svc-a",
            "https://github.com/org/svc-b",
        ])
        assert result["estimated_total_cost"] > 0
        assert result["estimated_total_tokens"] > 0
        assert result["model_used"] == "anthropic/claude-sonnet-4-6"
        assert len(result["per_repo_cost"]) == 2
        assert isinstance(result["exceeds_threshold"], bool)

    def test_estimate_with_local_paths(self, tmp_path: Path) -> None:
        repo_a = tmp_path / "svc-a"
        repo_a.mkdir()
        (repo_a / "main.py").write_text("class Service:\n    pass\n" * 50)
        (repo_a / "util.py").write_text("def helper(): return 1\n" * 100)

        estimator = CostEstimator(model="anthropic/claude-sonnet-4-6")
        result = estimator.estimate_for_repos(
            ["https://github.com/org/svc-a"],
            repo_paths={"https://github.com/org/svc-a": str(repo_a)},
        )
        assert result["estimated_total_tokens"] > 0
        assert result["per_repo_cost"]["https://github.com/org/svc-a"] > 0

    def test_exceeds_threshold_flag(self) -> None:
        estimator = CostEstimator(
            model="anthropic/claude-opus-4-6",  # expensive
            cost_threshold=0.001,  # very low threshold
        )
        result = estimator.estimate_for_repos(["https://github.com/org/repo"])
        assert result["exceeds_threshold"] is True

    def test_below_threshold_flag(self) -> None:
        estimator = CostEstimator(
            model="anthropic/claude-haiku-4-5",  # cheap
            cost_threshold=1000.0,  # very high threshold
        )
        result = estimator.estimate_for_repos(["https://github.com/org/repo"])
        assert result["exceeds_threshold"] is False

    def test_per_repo_costs_sum_to_total(self) -> None:
        estimator = CostEstimator(model="anthropic/claude-sonnet-4-6")
        result = estimator.estimate_for_repos([
            "https://github.com/org/a",
            "https://github.com/org/b",
            "https://github.com/org/c",
        ])
        summed = round(sum(result["per_repo_cost"].values()), 4)
        assert summed == result["estimated_total_cost"]

    def test_different_models_produce_different_costs(self) -> None:
        cheap = CostEstimator(model="anthropic/claude-haiku-4-5")
        expensive = CostEstimator(model="anthropic/claude-opus-4-6")
        repos = ["https://github.com/org/repo"]
        assert (
            expensive.estimate_for_repos(repos)["estimated_total_cost"]
            > cheap.estimate_for_repos(repos)["estimated_total_cost"]
        )
