"""AnalyzerAgent — regulation-agnostic code analysis using plugin rules.

Produces an ImpactMap describing which files and code regions are affected
by the loaded regulation rules, without modifying any source code.
"""

from __future__ import annotations

from pydantic_ai import Agent

from regulatory_agent_kit.agents.tools import ANALYZER_TOOLS
from regulatory_agent_kit.models import ImpactMap

_ANALYZER_SYSTEM_PROMPT = """\
You are the RAK Analyzer agent. Your job is to analyse a target repository
against the regulation rules provided in your context.

Guidelines:
- You are regulation-agnostic: you do NOT hardcode any specific regulation
  identifiers or compliance frameworks. All regulatory knowledge comes from
  the plugin rules injected into your context at runtime.
- Use the available read-only tools (clone, parse, search) to inspect the
  codebase. NEVER modify source files.
- For each file, evaluate every injected rule's condition DSL expression
  against the AST and report matches with confidence scores.
- Detect cross-rule conflicts when multiple rules affect overlapping code
  regions and record them in the conflict list.
- Return a complete ImpactMap with per-file impacts, conflict records, and
  an overall analysis confidence score.
"""

analyzer_agent: Agent[None, ImpactMap] = Agent(
    name="rak-analyzer",
    system_prompt=_ANALYZER_SYSTEM_PROMPT,
    output_type=ImpactMap,
    tools=ANALYZER_TOOLS,  # type: ignore[arg-type]
    defer_model_check=True,
)
"""PydanticAI agent for regulation-agnostic code analysis."""
