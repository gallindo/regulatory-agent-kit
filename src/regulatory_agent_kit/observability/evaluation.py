"""MLflow-based evaluation framework for agent outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScorerConfig:
    """Configuration for an evaluation scorer."""

    name: str
    scorer_type: str  # "builtin" or "llm_judge"
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Result from an evaluation run."""

    experiment_name: str
    metrics: dict[str, float]
    per_row_results: list[dict[str, Any]] = field(default_factory=list)
    run_id: str = ""


@dataclass
class AgentEvaluator:
    """Evaluate agent outputs using MLflow's evaluation framework."""

    experiment_name: str = "rak-agent-evaluation"
    tracking_uri: str = "http://localhost:5000"

    def _get_mlflow(self) -> Any:
        """Import and configure mlflow."""
        import mlflow

        mlflow.set_tracking_uri(self.tracking_uri)
        mlflow.set_experiment(self.experiment_name)
        return mlflow

    def evaluate(
        self,
        data: list[dict[str, Any]],
        *,
        scorers: list[ScorerConfig] | None = None,
        model_id: str = "",
    ) -> EvaluationResult:
        """Evaluate agent outputs against expected results.

        Args:
            data: List of dicts with 'inputs', 'outputs', and optionally
                'expectations'.
            scorers: Scorer configurations to use.
            model_id: Model identifier for tracking.

        Returns:
            EvaluationResult with metrics and per-row details.
        """
        mlflow = self._get_mlflow()

        scorer_objects = self._build_scorers(scorers or [], mlflow)

        with mlflow.start_run() as run:
            if model_id:
                mlflow.log_param("model_id", model_id)

            eval_data = mlflow.data.from_list(data)

            results = mlflow.genai.evaluate(
                data=eval_data,
                scorers=scorer_objects,
            )

            metrics = {k: float(v) for k, v in results.metrics.items() if v is not None}

            per_row: list[dict[str, Any]] = []
            if hasattr(results, "tables") and "eval_results" in results.tables:
                per_row = results.tables["eval_results"].to_dict("records")

            return EvaluationResult(
                experiment_name=self.experiment_name,
                metrics=metrics,
                per_row_results=per_row,
                run_id=run.info.run_id,
            )

    def _build_scorers(self, configs: list[ScorerConfig], mlflow: Any) -> list[Any]:
        """Build scorer objects from configurations."""
        scorers: list[Any] = []
        for config in configs:
            if config.scorer_type == "builtin":
                scorer = self._get_builtin_scorer(config, mlflow)
                if scorer is not None:
                    scorers.append(scorer)
            elif config.scorer_type == "llm_judge":
                scorer = self._build_llm_judge(config, mlflow)
                if scorer is not None:
                    scorers.append(scorer)
        return scorers

    def _get_builtin_scorer(self, config: ScorerConfig, mlflow: Any) -> Any | None:
        """Get a built-in MLflow scorer by name."""
        try:
            scorer_fn = getattr(mlflow.genai.scorers, config.name, None)
            if scorer_fn is None:
                logger.warning("Built-in scorer '%s' not found", config.name)
                return None
            return scorer_fn(**config.parameters) if config.parameters else scorer_fn()
        except Exception:
            logger.warning(
                "Failed to create built-in scorer '%s'",
                config.name,
                exc_info=True,
            )
            return None

    def _build_llm_judge(self, config: ScorerConfig, mlflow: Any) -> Any | None:
        """Build an LLM-as-a-judge scorer."""
        try:
            prompt_template = config.parameters.get("prompt_template", "")
            model = config.parameters.get("model", "")

            filtered_params = {
                k: v for k, v in config.parameters.items() if k not in ("prompt_template", "model")
            }

            return mlflow.genai.scorers.make_genai_metric(
                name=config.name,
                definition=prompt_template,
                model=model,
                **filtered_params,
            )
        except Exception:
            logger.warning(
                "Failed to create LLM judge scorer '%s'",
                config.name,
                exc_info=True,
            )
            return None

    def compare_experiments(
        self,
        experiment_names: list[str],
        metric_key: str = "",
    ) -> dict[str, Any]:
        """Compare metrics across experiments.

        Args:
            experiment_names: List of experiment names to compare.
            metric_key: Specific metric to compare (empty = all).

        Returns:
            Dict with experiment comparisons.
        """
        mlflow = self._get_mlflow()
        comparisons: dict[str, Any] = {"experiments": {}}

        for name in experiment_names:
            experiment = mlflow.get_experiment_by_name(name)
            if not experiment:
                logger.warning("Experiment '%s' not found", name)
                continue

            runs = mlflow.search_runs(
                experiment_ids=[experiment.experiment_id],
                order_by=["start_time DESC"],
                max_results=10,
            )

            if runs.empty:
                comparisons["experiments"][name] = {
                    "runs": 0,
                    "metrics": {},
                }
                continue

            metric_cols = [c for c in runs.columns if c.startswith("metrics.")]
            if metric_key:
                metric_cols = [c for c in metric_cols if metric_key in c]

            exp_metrics: dict[str, dict[str, float]] = {}
            for col in metric_cols:
                metric_name = col.replace("metrics.", "")
                values = runs[col].dropna()
                if not values.empty:
                    exp_metrics[metric_name] = {
                        "mean": float(values.mean()),
                        "min": float(values.min()),
                        "max": float(values.max()),
                        "latest": float(values.iloc[0]),
                    }

            comparisons["experiments"][name] = {
                "runs": len(runs),
                "metrics": exp_metrics,
            }

        return comparisons
