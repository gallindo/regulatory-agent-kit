"""Tests for the MLflow evaluation framework."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from regulatory_agent_kit.observability.evaluation import (
    AgentEvaluator,
    EvaluationResult,
    ScorerConfig,
)

# ---------------------------------------------------------------------------
# Data structure tests
# ---------------------------------------------------------------------------


class TestScorerConfig:
    """Tests for ScorerConfig dataclass."""

    def test_create_builtin_scorer_config(self) -> None:
        config = ScorerConfig(name="relevance", scorer_type="builtin")
        assert config.name == "relevance"
        assert config.scorer_type == "builtin"
        assert config.parameters == {}

    def test_create_llm_judge_scorer_config(self) -> None:
        params = {"prompt_template": "Rate quality", "model": "gpt-4"}
        config = ScorerConfig(name="quality", scorer_type="llm_judge", parameters=params)
        assert config.name == "quality"
        assert config.scorer_type == "llm_judge"
        assert config.parameters["prompt_template"] == "Rate quality"
        assert config.parameters["model"] == "gpt-4"

    def test_parameters_default_to_empty_dict(self) -> None:
        config = ScorerConfig(name="test", scorer_type="builtin")
        assert config.parameters == {}
        # Verify each instance gets its own dict
        config2 = ScorerConfig(name="test2", scorer_type="builtin")
        config.parameters["key"] = "value"
        assert "key" not in config2.parameters


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_create_with_metrics(self) -> None:
        result = EvaluationResult(
            experiment_name="test-exp",
            metrics={"accuracy": 0.95, "relevance": 0.88},
            run_id="abc123",
        )
        assert result.experiment_name == "test-exp"
        assert result.metrics["accuracy"] == 0.95
        assert result.metrics["relevance"] == 0.88
        assert result.run_id == "abc123"

    def test_defaults(self) -> None:
        result = EvaluationResult(experiment_name="exp", metrics={"score": 1.0})
        assert result.per_row_results == []
        assert result.run_id == ""

    def test_with_per_row_results(self) -> None:
        rows = [
            {"input": "q1", "output": "a1", "score": 0.9},
            {"input": "q2", "output": "a2", "score": 0.7},
        ]
        result = EvaluationResult(
            experiment_name="exp",
            metrics={"mean_score": 0.8},
            per_row_results=rows,
        )
        assert len(result.per_row_results) == 2
        assert result.per_row_results[0]["score"] == 0.9


# ---------------------------------------------------------------------------
# AgentEvaluator tests
# ---------------------------------------------------------------------------


class TestAgentEvaluatorInit:
    """Tests for AgentEvaluator initialization."""

    def test_default_values(self) -> None:
        evaluator = AgentEvaluator()
        assert evaluator.experiment_name == "rak-agent-evaluation"
        assert evaluator.tracking_uri == "http://localhost:5000"

    def test_custom_values(self) -> None:
        evaluator = AgentEvaluator(
            experiment_name="custom-exp",
            tracking_uri="http://mlflow:5555",
        )
        assert evaluator.experiment_name == "custom-exp"
        assert evaluator.tracking_uri == "http://mlflow:5555"


def _make_mock_mlflow() -> MagicMock:
    """Create a consistently structured mock mlflow module."""
    mock = MagicMock()
    mock.genai = MagicMock()
    mock.genai.scorers = MagicMock()
    mock.data = MagicMock()
    return mock


class TestBuildScorers:
    """Tests for AgentEvaluator._build_scorers."""

    def test_empty_configs_returns_empty(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        result = evaluator._build_scorers([], mock_mlflow)
        assert result == []

    def test_builtin_scorer_created(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        mock_scorer = MagicMock()
        mock_mlflow.genai.scorers.relevance = MagicMock(return_value=mock_scorer)

        config = ScorerConfig(name="relevance", scorer_type="builtin")
        result = evaluator._build_scorers([config], mock_mlflow)

        assert len(result) == 1
        assert result[0] is mock_scorer

    def test_builtin_scorer_with_parameters(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        mock_scorer = MagicMock()
        mock_mlflow.genai.scorers.custom_metric = MagicMock(return_value=mock_scorer)

        config = ScorerConfig(
            name="custom_metric",
            scorer_type="builtin",
            parameters={"threshold": 0.5},
        )
        result = evaluator._build_scorers([config], mock_mlflow)

        assert len(result) == 1
        mock_mlflow.genai.scorers.custom_metric.assert_called_once_with(threshold=0.5)

    def test_builtin_scorer_not_found_returns_empty(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        mock_mlflow.genai.scorers.nonexistent = None

        config = ScorerConfig(name="nonexistent", scorer_type="builtin")
        result = evaluator._build_scorers([config], mock_mlflow)
        assert result == []

    def test_builtin_scorer_exception_returns_empty(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        mock_mlflow.genai.scorers.bad_scorer = MagicMock(side_effect=RuntimeError("boom"))

        config = ScorerConfig(name="bad_scorer", scorer_type="builtin")
        result = evaluator._build_scorers([config], mock_mlflow)
        assert result == []

    def test_llm_judge_scorer_created(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        mock_scorer = MagicMock()
        mock_mlflow.genai.scorers.make_genai_metric = MagicMock(return_value=mock_scorer)

        config = ScorerConfig(
            name="compliance_check",
            scorer_type="llm_judge",
            parameters={
                "prompt_template": "Rate compliance",
                "model": "gpt-4",
            },
        )
        result = evaluator._build_scorers([config], mock_mlflow)

        assert len(result) == 1
        assert result[0] is mock_scorer
        mock_mlflow.genai.scorers.make_genai_metric.assert_called_once_with(
            name="compliance_check",
            definition="Rate compliance",
            model="gpt-4",
        )

    def test_llm_judge_with_extra_params(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        mock_scorer = MagicMock()
        mock_mlflow.genai.scorers.make_genai_metric = MagicMock(return_value=mock_scorer)

        config = ScorerConfig(
            name="judge",
            scorer_type="llm_judge",
            parameters={
                "prompt_template": "Template",
                "model": "claude-3",
                "grading_notes": "Be strict",
            },
        )
        result = evaluator._build_scorers([config], mock_mlflow)

        assert len(result) == 1
        mock_mlflow.genai.scorers.make_genai_metric.assert_called_once_with(
            name="judge",
            definition="Template",
            model="claude-3",
            grading_notes="Be strict",
        )

    def test_llm_judge_exception_returns_empty(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        mock_mlflow.genai.scorers.make_genai_metric = MagicMock(
            side_effect=ValueError("bad config")
        )

        config = ScorerConfig(
            name="bad_judge",
            scorer_type="llm_judge",
            parameters={"prompt_template": "x", "model": "y"},
        )
        result = evaluator._build_scorers([config], mock_mlflow)
        assert result == []

    def test_unknown_scorer_type_ignored(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()

        config = ScorerConfig(name="x", scorer_type="unknown_type")
        result = evaluator._build_scorers([config], mock_mlflow)
        assert result == []

    def test_mixed_scorers(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        builtin_scorer = MagicMock(name="builtin_result")
        judge_scorer = MagicMock(name="judge_result")
        mock_mlflow.genai.scorers.relevance = MagicMock(return_value=builtin_scorer)
        mock_mlflow.genai.scorers.make_genai_metric = MagicMock(return_value=judge_scorer)

        configs = [
            ScorerConfig(name="relevance", scorer_type="builtin"),
            ScorerConfig(
                name="custom",
                scorer_type="llm_judge",
                parameters={"prompt_template": "T", "model": "M"},
            ),
        ]
        result = evaluator._build_scorers(configs, mock_mlflow)
        assert len(result) == 2
        assert result[0] is builtin_scorer
        assert result[1] is judge_scorer


class TestEvaluate:
    """Tests for AgentEvaluator.evaluate."""

    def _setup_mock_mlflow(self) -> MagicMock:
        """Create mock mlflow with evaluate support."""
        mock_mlflow = _make_mock_mlflow()

        # Mock run context manager
        mock_run = MagicMock()
        mock_run.info.run_id = "run-123"
        mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=mock_run)
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

        # Mock evaluate results
        mock_results = MagicMock()
        mock_results.metrics = {"accuracy": 0.95, "relevance": 0.88}
        mock_results.tables = {}
        mock_mlflow.genai.evaluate.return_value = mock_results

        return mock_mlflow

    def test_evaluate_returns_result(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = self._setup_mock_mlflow()

        data = [
            {"inputs": "q1", "outputs": "a1"},
            {"inputs": "q2", "outputs": "a2"},
        ]

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.evaluate(data)

        assert isinstance(result, EvaluationResult)
        assert result.experiment_name == "rak-agent-evaluation"
        assert result.metrics["accuracy"] == 0.95
        assert result.metrics["relevance"] == 0.88
        assert result.run_id == "run-123"

    def test_evaluate_with_model_id(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = self._setup_mock_mlflow()

        data = [{"inputs": "q1", "outputs": "a1"}]

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            evaluator.evaluate(data, model_id="claude-3-opus")

        mock_mlflow.log_param.assert_called_once_with("model_id", "claude-3-opus")

    def test_evaluate_without_model_id_skips_log_param(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = self._setup_mock_mlflow()

        data = [{"inputs": "q1", "outputs": "a1"}]

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            evaluator.evaluate(data)

        mock_mlflow.log_param.assert_not_called()

    def test_evaluate_with_scorers(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = self._setup_mock_mlflow()
        mock_scorer = MagicMock()
        mock_mlflow.genai.scorers.relevance = MagicMock(return_value=mock_scorer)

        data = [{"inputs": "q1", "outputs": "a1"}]
        scorers = [ScorerConfig(name="relevance", scorer_type="builtin")]

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            evaluator.evaluate(data, scorers=scorers)

        # Verify scorer was passed to evaluate
        call_kwargs = mock_mlflow.genai.evaluate.call_args
        assert mock_scorer in call_kwargs.kwargs["scorers"]

    def test_evaluate_filters_none_metrics(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = self._setup_mock_mlflow()
        mock_mlflow.genai.evaluate.return_value.metrics = {
            "good": 0.9,
            "bad": None,
        }

        data = [{"inputs": "q1", "outputs": "a1"}]

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.evaluate(data)

        assert "good" in result.metrics
        assert "bad" not in result.metrics

    def test_evaluate_extracts_per_row_results(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = self._setup_mock_mlflow()

        mock_table = MagicMock()
        mock_table.to_dict.return_value = [
            {"input": "q1", "score": 0.9},
            {"input": "q2", "score": 0.7},
        ]
        mock_mlflow.genai.evaluate.return_value.tables = {"eval_results": mock_table}

        data = [{"inputs": "q1", "outputs": "a1"}]

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.evaluate(data)

        assert len(result.per_row_results) == 2
        mock_table.to_dict.assert_called_once_with("records")

    def test_evaluate_handles_missing_tables(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = self._setup_mock_mlflow()
        # Results without tables attribute
        del mock_mlflow.genai.evaluate.return_value.tables

        data = [{"inputs": "q1", "outputs": "a1"}]

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.evaluate(data)

        assert result.per_row_results == []

    def test_evaluate_calls_data_from_list(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = self._setup_mock_mlflow()

        data = [{"inputs": "q1", "outputs": "a1"}]

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            evaluator.evaluate(data)

        mock_mlflow.data.from_list.assert_called_once_with(data)


class TestCompareExperiments:
    """Tests for AgentEvaluator.compare_experiments."""

    def _make_mock_runs(self, metric_data: dict[str, list[float | None]]) -> MagicMock:
        """Create a mock DataFrame-like object for search_runs."""
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.__len__ = MagicMock(return_value=len(next(iter(metric_data.values()))))

        columns = [f"metrics.{k}" for k in metric_data]
        mock_df.columns = columns

        def getitem(_self: Any, key: str) -> Any:
            metric_name = key.replace("metrics.", "")
            values = metric_data[metric_name]
            series = MagicMock()
            non_null = [v for v in values if v is not None]
            series.dropna.return_value = series
            series.empty = len(non_null) == 0
            if non_null:
                series.mean.return_value = sum(non_null) / len(non_null)
                series.min.return_value = min(non_null)
                series.max.return_value = max(non_null)
                series.iloc.__getitem__ = MagicMock(return_value=non_null[0])
            return series

        mock_df.__getitem__ = getitem
        return mock_df

    def test_compare_single_experiment(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()

        mock_exp = MagicMock()
        mock_exp.experiment_id = "exp-1"
        mock_mlflow.get_experiment_by_name.return_value = mock_exp

        mock_runs = self._make_mock_runs({"accuracy": [0.9, 0.85, 0.88]})
        mock_mlflow.search_runs.return_value = mock_runs

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.compare_experiments(["test-exp"])

        assert "test-exp" in result["experiments"]
        exp_data = result["experiments"]["test-exp"]
        assert exp_data["runs"] == 3
        assert "accuracy" in exp_data["metrics"]

    def test_compare_experiment_not_found(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()
        mock_mlflow.get_experiment_by_name.return_value = None

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.compare_experiments(["missing-exp"])

        assert "missing-exp" not in result["experiments"]

    def test_compare_experiment_no_runs(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()

        mock_exp = MagicMock()
        mock_exp.experiment_id = "exp-1"
        mock_mlflow.get_experiment_by_name.return_value = mock_exp

        mock_runs = MagicMock()
        mock_runs.empty = True
        mock_mlflow.search_runs.return_value = mock_runs

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.compare_experiments(["empty-exp"])

        assert result["experiments"]["empty-exp"] == {
            "runs": 0,
            "metrics": {},
        }

    def test_compare_with_metric_key_filter(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()

        mock_exp = MagicMock()
        mock_exp.experiment_id = "exp-1"
        mock_mlflow.get_experiment_by_name.return_value = mock_exp

        mock_runs = self._make_mock_runs(
            {
                "accuracy": [0.9, 0.85],
                "relevance": [0.7, 0.75],
            }
        )
        mock_mlflow.search_runs.return_value = mock_runs

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.compare_experiments(["test-exp"], metric_key="accuracy")

        exp_data = result["experiments"]["test-exp"]
        # Only accuracy metric should be present
        assert "accuracy" in exp_data["metrics"]
        assert "relevance" not in exp_data["metrics"]

    def test_compare_multiple_experiments(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()

        exps = {"exp-a": "id-a", "exp-b": "id-b"}

        def get_exp(name: str) -> MagicMock | None:
            if name in exps:
                mock = MagicMock()
                mock.experiment_id = exps[name]
                return mock
            return None

        mock_mlflow.get_experiment_by_name.side_effect = get_exp
        mock_mlflow.search_runs.return_value = self._make_mock_runs({"score": [0.8, 0.9]})

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.compare_experiments(["exp-a", "exp-b"])

        assert "exp-a" in result["experiments"]
        assert "exp-b" in result["experiments"]

    def test_compare_metric_statistics(self) -> None:
        evaluator = AgentEvaluator()
        mock_mlflow = _make_mock_mlflow()

        mock_exp = MagicMock()
        mock_exp.experiment_id = "exp-1"
        mock_mlflow.get_experiment_by_name.return_value = mock_exp

        mock_runs = self._make_mock_runs({"score": [0.9, 0.7, 0.8]})
        mock_mlflow.search_runs.return_value = mock_runs

        with patch.object(evaluator, "_get_mlflow", return_value=mock_mlflow):
            result = evaluator.compare_experiments(["stats-exp"])

        metrics = result["experiments"]["stats-exp"]["metrics"]["score"]
        assert "mean" in metrics
        assert "min" in metrics
        assert "max" in metrics
        assert "latest" in metrics


class TestGetMlflow:
    """Tests for AgentEvaluator._get_mlflow."""

    def test_get_mlflow_configures_tracking(self) -> None:
        evaluator = AgentEvaluator(
            experiment_name="my-exp",
            tracking_uri="http://mlflow:5000",
        )

        mock_mlflow = MagicMock()
        with (
            patch.dict("sys.modules", {"mlflow": mock_mlflow}),
            patch(
                "regulatory_agent_kit.observability.evaluation.import_module",
                create=True,
            ),
            patch("builtins.__import__", return_value=mock_mlflow),
        ):
            result = evaluator._get_mlflow()

        mock_mlflow.set_tracking_uri.assert_called_once_with("http://mlflow:5000")
        mock_mlflow.set_experiment.assert_called_once_with("my-exp")
        assert result is mock_mlflow
