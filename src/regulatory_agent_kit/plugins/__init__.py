"""Plugin system — load, validate, and parse regulation YAML plugins."""

from regulatory_agent_kit.plugins.condition_dsl import (
    ConditionAST,
    ConditionVisitor,
    LLMPromptVisitor,
    Predicate,
    StaticEvaluabilityVisitor,
    can_evaluate_statically,
    parse,
    to_llm_prompt,
)
from regulatory_agent_kit.plugins.conflict_engine import ConflictEngine
from regulatory_agent_kit.plugins.loader import PluginLoader, TemplateValidator
from regulatory_agent_kit.plugins.scaffolder import PluginScaffolder
from regulatory_agent_kit.plugins.schema import (
    RTS,
    AffectsClause,
    CrossReference,
    EventTrigger,
    RegulationPlugin,
    Remediation,
    Rule,
)

__all__ = [
    "RTS",
    "AffectsClause",
    "ConditionAST",
    "ConditionVisitor",
    "ConflictEngine",
    "CrossReference",
    "EventTrigger",
    "LLMPromptVisitor",
    "PluginLoader",
    "PluginScaffolder",
    "Predicate",
    "RegulationPlugin",
    "Remediation",
    "Rule",
    "StaticEvaluabilityVisitor",
    "TemplateValidator",
    "can_evaluate_statically",
    "parse",
    "to_llm_prompt",
]
