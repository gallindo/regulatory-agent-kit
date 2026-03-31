"""Tests for Grafana dashboard JSON validity."""

import json
from pathlib import Path

import pytest

DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "docker" / "grafana" / "dashboards"


class TestDashboardFiles:
    """Validate structure of each Grafana dashboard JSON file."""

    @pytest.fixture(
        params=[
            "pipeline-throughput.json",
            "error-rates.json",
            "llm-cost-tracking.json",
        ],
    )
    def dashboard(self, request: pytest.FixtureRequest) -> dict:
        """Load a dashboard JSON file."""
        path = DASHBOARD_DIR / request.param
        assert path.exists(), f"Dashboard file missing: {request.param}"
        with path.open() as f:
            return json.load(f)

    def test_has_required_fields(self, dashboard: dict) -> None:
        """Every dashboard must have a title and at least one panel."""
        assert "title" in dashboard
        assert "panels" in dashboard
        assert isinstance(dashboard["panels"], list)
        assert len(dashboard["panels"]) > 0

    def test_panels_have_targets(self, dashboard: dict) -> None:
        """Non-row panels must define query targets."""
        for panel in dashboard["panels"]:
            if panel.get("type") == "row":
                continue
            assert "targets" in panel or "panels" in panel, (
                f"Panel '{panel.get('title')}' has no targets"
            )

    def test_panels_have_titles(self, dashboard: dict) -> None:
        """Every panel must have a title."""
        for panel in dashboard["panels"]:
            assert "title" in panel, f"Panel missing title: {panel}"

    def test_datasource_is_prometheus(self, dashboard: dict) -> None:
        """All query targets must use the Prometheus datasource."""
        for panel in dashboard["panels"]:
            if panel.get("type") == "row":
                continue
            for target in panel.get("targets", []):
                ds = target.get("datasource", {})
                if isinstance(ds, dict):
                    assert ds.get("type") == "prometheus", (
                        f"Non-Prometheus datasource in panel '{panel.get('title')}'"
                    )


class TestDashboardProvisioning:
    """Validate the Grafana dashboard provisioning configuration."""

    def test_provisioning_config_exists(self) -> None:
        """The dashboards.yml provisioning file must exist."""
        config_path = (
            Path(__file__).resolve().parents[2]
            / "docker"
            / "grafana"
            / "provisioning"
            / "dashboards"
            / "dashboards.yml"
        )
        assert config_path.exists()
