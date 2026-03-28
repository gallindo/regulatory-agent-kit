"""RefactorAgent — applies remediation strategies from plugin rules.

Produces a ChangeSet containing branch, diffs, and commit information
for the code modifications required to achieve compliance.
"""

from __future__ import annotations

from pydantic_ai import Agent

from regulatory_agent_kit.agents.tools import REFACTOR_TOOLS
from regulatory_agent_kit.models import ChangeSet

_REFACTOR_SYSTEM_PROMPT = """\
You are the RAK Refactor agent. Your job is to apply remediation changes to
a target repository based on the ImpactMap and regulation plugin rules
provided in your context.

Guidelines:
- You are regulation-agnostic: all remediation strategies (add_annotation,
  add_configuration, replace_pattern, add_dependency, generate_file,
  custom_agent) come from the plugin rules — never invent compliance logic.
- Create a dedicated branch for all changes.
- Apply each remediation using the available read-write tools (branch,
  commit, AST transform, template render).
- For each file diff, record the rule ID, strategy used, and a confidence
  score indicating how certain you are that the change is correct.
- Commit all changes with a descriptive message referencing the rule IDs.
- Return a complete ChangeSet with the branch name, per-file diffs,
  confidence scores, and the resulting commit SHA.
"""

refactor_agent: Agent[None, ChangeSet] = Agent(
    name="rak-refactor",
    system_prompt=_REFACTOR_SYSTEM_PROMPT,
    output_type=ChangeSet,
    tools=REFACTOR_TOOLS,  # type: ignore[arg-type]
    defer_model_check=True,
)
"""PydanticAI agent for applying regulation-driven code remediation."""
