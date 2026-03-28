"""TestGeneratorAgent — generates and runs compliance tests.

Produces a TestResult summarising test execution outcomes for the
remediation changes applied by the RefactorAgent.
"""

from __future__ import annotations

from pydantic_ai import Agent

from regulatory_agent_kit.agents.tools import TEST_GENERATOR_TOOLS
from regulatory_agent_kit.models import TestResult

_TEST_GENERATOR_SYSTEM_PROMPT = """\
You are the RAK Test Generator agent. Your job is to generate and execute
compliance tests that verify the remediation changes are correct and do not
introduce regressions.

Guidelines:
- You are regulation-agnostic: test expectations are derived from the plugin
  rules and ImpactMap provided in your context — never hardcode regulation
  identifiers or compliance criteria.
- Use the available sandboxed tools (read files, run tests, render test
  templates) to create and execute test suites.
- Generate test files using Jinja2 templates where appropriate.
- Execute the generated tests in a sandboxed environment and collect results.
- Report the pass rate, total/passed/failed counts, and details of any
  failures including test name, file path, error message, and stack trace.
- Return a complete TestResult with all execution metrics and a list of
  created test file paths.
"""

test_generator_agent: Agent[None, TestResult] = Agent(
    name="rak-test-generator",
    system_prompt=_TEST_GENERATOR_SYSTEM_PROMPT,
    output_type=TestResult,
    tools=TEST_GENERATOR_TOOLS,  # type: ignore[arg-type]
    defer_model_check=True,
)
"""PydanticAI agent for compliance test generation and execution."""
