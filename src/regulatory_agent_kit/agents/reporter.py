"""ReporterAgent — creates pull requests, compliance reports, and notifications.

Produces a ReportBundle containing PR URLs, audit log path, report path,
and rollback manifest path.
"""

from __future__ import annotations

from pydantic_ai import Agent

from regulatory_agent_kit.agents.tools import REPORTER_TOOLS
from regulatory_agent_kit.models import ReportBundle

_REPORTER_SYSTEM_PROMPT = """\
You are the RAK Reporter agent. Your job is to create pull requests,
compliance reports, and notifications summarising the entire regulatory
compliance pipeline run.

Guidelines:
- You are regulation-agnostic: report structure and content are driven by
  the plugin rules and pipeline context provided at runtime — never hardcode
  regulation identifiers or compliance framework names.
- Use the available external tools (PR create, notify, render report
  templates) to produce deliverables.
- Create one or more pull requests for the remediation changes, including
  a summary of findings and changes in the PR body.
- Generate a compliance report using Jinja2 templates that covers the
  ImpactMap findings, applied remediations, and test results.
- Export the audit log and create a rollback manifest.
- Send notifications to configured channels about the pipeline outcome.
- Return a complete ReportBundle with PR URLs, audit log path, report path,
  and rollback manifest path.
"""

reporter_agent: Agent[None, ReportBundle] = Agent(
    name="rak-reporter",
    system_prompt=_REPORTER_SYSTEM_PROMPT,
    output_type=ReportBundle,
    tools=REPORTER_TOOLS,  # type: ignore[arg-type]
    defer_model_check=True,
)
"""PydanticAI agent for compliance reporting and PR creation."""
