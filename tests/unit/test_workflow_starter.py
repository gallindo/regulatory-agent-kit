"""Unit tests for WorkflowStarter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from regulatory_agent_kit.event_sources.starter import WorkflowStarter
from regulatory_agent_kit.exceptions import EventSourceError
from regulatory_agent_kit.models.events import RegulatoryEvent


def _make_event() -> RegulatoryEvent:
    return RegulatoryEvent(
        regulation_id="example-regulation-2025",
        change_type="new_requirement",
        source="test",
    )


def _mock_client() -> AsyncMock:
    """Return a mocked Temporal Client."""
    client = AsyncMock()
    client.start_workflow = AsyncMock(return_value=None)
    client.get_workflow_handle = MagicMock()
    return client


class TestWorkflowStarter:
    """Tests for the Temporal workflow starter."""

    async def test_start_pipeline_returns_workflow_id(self) -> None:
        client = _mock_client()
        starter = WorkflowStarter(client)
        event = _make_event()

        wf_id = await starter.start_pipeline(event, {"plugin": "data"}, {"key": "val"})

        assert wf_id.startswith("rak-pipeline-")
        client.start_workflow.assert_awaited_once()

    async def test_start_pipeline_raises_on_failure(self) -> None:
        client = _mock_client()
        client.start_workflow.side_effect = RuntimeError("connection failed")
        starter = WorkflowStarter(client)

        with pytest.raises(EventSourceError, match="Failed to start"):
            await starter.start_pipeline(_make_event(), {}, {})

    async def test_signal_approval(self) -> None:
        client = _mock_client()
        handle = AsyncMock()
        client.get_workflow_handle.return_value = handle
        starter = WorkflowStarter(client)

        await starter.signal_approval("wf-123", {"approved": True})

        client.get_workflow_handle.assert_called_once_with("wf-123")
        handle.signal.assert_awaited_once_with("approval", {"approved": True})

    async def test_signal_approval_raises_on_failure(self) -> None:
        client = _mock_client()
        handle = AsyncMock()
        handle.signal.side_effect = RuntimeError("not found")
        client.get_workflow_handle.return_value = handle
        starter = WorkflowStarter(client)

        with pytest.raises(EventSourceError, match="Failed to signal"):
            await starter.signal_approval("wf-bad", {"approved": False})

    async def test_query_status(self) -> None:
        client = _mock_client()
        handle = AsyncMock()
        handle.query.return_value = {"status": "running", "phase": "ANALYZING"}
        client.get_workflow_handle.return_value = handle
        starter = WorkflowStarter(client)

        result = await starter.query_status("wf-123")

        assert result == {"status": "running", "phase": "ANALYZING"}
        handle.query.assert_awaited_once_with("status")

    async def test_cancel(self) -> None:
        client = _mock_client()
        handle = AsyncMock()
        client.get_workflow_handle.return_value = handle
        starter = WorkflowStarter(client)

        await starter.cancel("wf-123")

        handle.cancel.assert_awaited_once()

    async def test_cancel_raises_on_failure(self) -> None:
        client = _mock_client()
        handle = AsyncMock()
        handle.cancel.side_effect = RuntimeError("boom")
        client.get_workflow_handle.return_value = handle
        starter = WorkflowStarter(client)

        with pytest.raises(EventSourceError, match="Failed to cancel"):
            await starter.cancel("wf-bad")

    async def test_list_running(self) -> None:
        client = _mock_client()

        workflow1 = MagicMock()
        workflow1.id = "wf-1"
        workflow2 = MagicMock()
        workflow2.id = "wf-2"

        async def _mock_list(*_args: Any, **_kwargs: Any) -> Any:
            for wf in [workflow1, workflow2]:
                yield wf

        client.list_workflows = _mock_list
        starter = WorkflowStarter(client)

        result = await starter.list_running()
        assert result == ["wf-1", "wf-2"]
