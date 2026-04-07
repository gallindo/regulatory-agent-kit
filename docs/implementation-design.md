# regulatory-agent-kit — Low-Level Design / Detailed Design Document

> **Version:** 1.0
> **Date:** 2026-03-27
> **Status:** Active Development
> **Audience:** Software engineers implementing, extending, or reviewing the codebase.

---

## Table of Contents

1. [Document Purpose](#1-document-purpose)
2. [Class Diagrams](#2-class-diagrams)
3. [Detailed Sequence Diagrams](#3-detailed-sequence-diagrams)
4. [State Machine Diagrams](#4-state-machine-diagrams)
5. [Database Schema Details](#5-database-schema-details)
6. [Algorithms and Business Logic](#6-algorithms-and-business-logic)
7. [Error Handling and Retry Logic](#7-error-handling-and-retry-logic)

---

## 1. Document Purpose

This Low-Level Design (LLD) document describes the internal structure and behavior of `regulatory-agent-kit` at the class, method, and algorithm level. It is the most granular design document, intended for engineers writing or reviewing code.

| Document | Abstraction Level | This LLD Adds |
|---|---|---|
| [`framework-spec.md`](framework-spec.md) | Conceptual — what the system does | N/A |
| [`software-architecture.md`](software-architecture.md) | Structural — C4 model, components, data architecture | N/A |
| [`system-design.md`](system-design.md) | Physical — deployment, hardware, integrations, data flows | N/A |
| **This document** | **Behavioral** — class hierarchies, method signatures, algorithms, state machines, error paths | Class diagrams, detailed sequence diagrams, algorithm pseudocode, state machines per component |

---

## 2. Class Diagrams

> **Pydantic v2 primer:** [Pydantic](https://docs.pydantic.dev/) is a Python data validation library. All data shapes in this project are `BaseModel` subclasses — Python classes with type-annotated fields that are automatically validated on construction. `model_validate()` parses raw data (dicts, JSON) into a typed model, raising errors if the data doesn't match. `Literal["a", "b"]` restricts a field to specific values. This pattern replaces manual validation, DTO classes, and schema definitions with a single source of truth. See also: [`glossary.md`](glossary.md).

### 2.1 Domain Models (`models/`)

All data shapes are Pydantic v2 `BaseModel` subclasses. These models are the single source of truth for serialization, validation, API schemas, and database DTOs.

```mermaid
classDiagram
    class RegulatoryEvent {
        +UUID event_id
        +datetime timestamp
        +str regulation_id
        +Literal~new_requirement,amendment,withdrawal~ change_type
        +str source
        +dict~str,Any~ payload
    }

    class PipelineInput {
        +str regulation_id
        +list~str~ repo_urls
        +RegulationPlugin plugin
        +PipelineConfig config
    }

    class PipelineConfig {
        +str default_model
        +float cost_threshold
        +bool auto_approve_cost
        +str checkpoint_mode
        +int max_retries
    }

    class PipelineResult {
        +UUID run_id
        +Literal~completed,rejected,failed,cost_rejected~ status
        +Optional~ReportBundle~ report
        +float actual_cost
    }

    class RepoInput {
        +str repo_url
        +RegulationPlugin plugin
        +Literal~analyze,refactor_and_test~ phase
        +Optional~ImpactMap~ impact_map
    }

    class RepoResult {
        +str repo_url
        +Literal~completed,failed,skipped~ status
        +Optional~str~ branch_name
        +Optional~str~ pr_url
        +Optional~str~ error
    }

    class ImpactMap {
        +list~FileImpact~ files
        +list~ConflictRecord~ conflicts
        +float analysis_confidence
    }

    class FileImpact {
        +str file_path
        +list~RuleMatch~ matched_rules
        +str suggested_approach
        +list~ASTRegion~ affected_regions
    }

    class RuleMatch {
        +str rule_id
        +str description
        +Literal~critical,high,medium,low~ severity
        +float confidence
        +str condition_evaluated
    }

    class ASTRegion {
        +int start_line
        +int end_line
        +int start_col
        +int end_col
        +str node_type
    }

    class ChangeSet {
        +str branch_name
        +list~FileDiff~ diffs
        +list~float~ confidence_scores
        +str commit_sha
    }

    class FileDiff {
        +str file_path
        +str rule_id
        +str diff_content
        +float confidence
        +str strategy_used
    }

    class TestResult {
        +float pass_rate
        +int total_tests
        +int passed
        +int failed
        +list~TestFailure~ failures
        +list~str~ test_files_created
    }

    class TestFailure {
        +str test_name
        +str file_path
        +str error_message
        +str stack_trace
    }

    class ReportBundle {
        +list~str~ pr_urls
        +str audit_log_path
        +str report_path
        +str rollback_manifest_path
    }

    class CheckpointDecision {
        +str actor
        +Literal~approved,rejected,modifications_requested~ decision
        +Optional~str~ rationale
        +str signature
        +datetime decided_at
    }

    class ConflictRecord {
        +list~str~ conflicting_rule_ids
        +list~ASTRegion~ affected_regions
        +str description
        +Optional~str~ resolution
    }

    PipelineInput --> PipelineConfig
    PipelineInput --> RegulationPlugin
    PipelineResult --> ReportBundle
    ImpactMap --> FileImpact
    ImpactMap --> ConflictRecord
    FileImpact --> RuleMatch
    FileImpact --> ASTRegion
    ChangeSet --> FileDiff
    TestResult --> TestFailure
    ConflictRecord --> ASTRegion
```

### 2.2 Plugin System (`plugins/`)

```mermaid
classDiagram
    class RegulationPlugin {
        +str id
        +str name
        +str version
        +date effective_date
        +str jurisdiction
        +str authority
        +HttpUrl source_url
        +str disclaimer
        +list~Rule~ rules
        +Optional~list~RTS~~ regulatory_technical_standards
        +Optional~list~CrossReference~~ cross_references
        +Optional~str~ supersedes
        +str changelog
        +Optional~EventTrigger~ event_trigger
        +dict~str,Any~ model_extra
        +validate_disclaimer()$ Validator
    }

    class Rule {
        +str id
        +str description
        +Literal~critical,high,medium,low~ severity
        +list~AffectsClause~ affects
        +Remediation remediation
        +dict~str,Any~ model_extra
    }

    class AffectsClause {
        +str pattern
        +str condition
    }

    class Remediation {
        +Literal~add_annotation,add_configuration,replace_pattern,add_dependency,generate_file,custom_agent~ strategy
        +Path template
        +Optional~Path~ test_template
        +float confidence_threshold
    }

    class CrossReference {
        +str regulation_id
        +Literal~does_not_override,takes_precedence,complementary,supersedes,references~ relationship
        +list~str~ articles
        +Optional~Literal~escalate_to_human,apply_both,defer_to_referenced~~ conflict_handling
    }

    class RTS {
        +str id
        +str name
        +HttpUrl url
    }

    class EventTrigger {
        +str topic
        +dict~str,str~ schema
    }

    class PluginLoader {
        -Path plugin_dir
        -dict~str,RegulationPlugin~ _cache
        +load(path: Path) RegulationPlugin
        +load_all() list~RegulationPlugin~
        +validate(path: Path) list~ValidationError~
        +get_by_id(id: str) Optional~RegulationPlugin~
        -_parse_yaml(path: Path) dict
        -_resolve_templates(plugin: RegulationPlugin, base_dir: Path) void
    }

    class ConditionDSL {
        +parse(expression: str) ConditionAST
        +evaluate(ast: ConditionAST, context: ASTContext) bool
        +can_evaluate_statically(ast: ConditionAST) bool
        +to_llm_prompt(ast: ConditionAST) str
    }

    class ConditionAST {
        +Literal~AND,OR,NOT,PREDICATE~ node_type
        +Optional~list~ConditionAST~~ children
        +Optional~Predicate~ predicate
    }

    class Predicate {
        +Literal~implements,inherits,has_annotation,has_decorator,has_method,has_key,matches~ operator
        +str argument
    }

    class ConflictEngine {
        +detect(plugins: list~RegulationPlugin~, impact_maps: dict~str,ImpactMap~) list~ConflictRecord~
        +get_precedence(plugin_a: str, plugin_b: str) Optional~str~
        -_find_overlapping_regions(map_a: ImpactMap, map_b: ImpactMap) list~tuple~
        -_check_relationship(ref: CrossReference) Literal~suppress,escalate,apply_both~
    }

    RegulationPlugin --> Rule
    RegulationPlugin --> CrossReference
    RegulationPlugin --> RTS
    RegulationPlugin --> EventTrigger
    Rule --> AffectsClause
    Rule --> Remediation
    PluginLoader --> RegulationPlugin
    ConditionDSL --> ConditionAST
    ConditionAST --> Predicate
    ConflictEngine --> RegulationPlugin
    ConflictEngine --> ConflictRecord
```

### 2.3 Workflow and Activity Layer (`workflows/`, `activities/`)

```mermaid
classDiagram
    class CompliancePipeline {
        -Optional~CheckpointDecision~ impact_review_decision
        -Optional~CheckpointDecision~ merge_review_decision
        -float cumulative_cost
        +run(input: PipelineInput) PipelineResult
        +approve_impact_review(decision: CheckpointDecision) void
        +approve_merge_review(decision: CheckpointDecision) void
        +query_status() PipelineStatus
        -_fan_out_analysis(repos: list~str~, plugin: RegulationPlugin) list~ImpactMap~
        -_fan_out_refactor(repos: list~str~, impact_map: ImpactMap) list~RepoResult~
        -_wait_for_approval(field: str) CheckpointDecision
    }

    class RepositoryProcessor {
        +run(input: RepoInput) RepoResult
        -_run_analyze(input: RepoInput) ImpactMap
        -_run_refactor_and_test(input: RepoInput) RepoResult
    }

    class AnalyzeActivity {
        +analyze_repository(input: AnalysisInput) ImpactMap
        -_clone_repo(url: str) Path
        -_match_rules(repo: Path, rules: list~Rule~) list~FileImpact~
        -_detect_conflicts(impacts: list~FileImpact~, cross_refs: list~CrossReference~) list~ConflictRecord~
    }

    class RefactorActivity {
        +refactor_repository(input: RefactorInput) ChangeSet
        -_create_branch(repo: Path, regulation_id: str, rule_id: str) str
        -_apply_template(file: Path, template: Path, context: dict) str
        -_compute_confidence(original: str, modified: str) float
    }

    class TestActivity {
        +test_repository(input: TestInput) TestResult
        -_generate_tests(change_set: ChangeSet, templates: list~Path~) list~str~
        -_execute_sandboxed(test_files: list~str~, repo: Path) TestResult
        -_validate_sandbox_config() void
    }

    class ReportActivity {
        +report_results(input: ReportInput) ReportBundle
        -_create_merge_requests(results: list~RepoResult~) list~str~
        -_generate_audit_log(entries: list~AuditEntry~) Path
        -_generate_compliance_report(results: list~RepoResult~) Path
        -_generate_rollback_manifest(branches: list~str~, prs: list~str~) Path
    }

    class CostEstimationActivity {
        +estimate_cost(input: PipelineInput) CostEstimate
        -_estimate_tokens_per_repo(repo_url: str, rules: list~Rule~) int
        -_calculate_cost(total_tokens: int, model: str) float
    }

    class CostEstimate {
        +float estimated_total_cost
        +dict~str,float~ per_repo_cost
        +int estimated_total_tokens
        +str model_used
        +bool exceeds_threshold
    }

    CompliancePipeline --> RepositoryProcessor : spawns child
    RepositoryProcessor --> AnalyzeActivity : executes
    RepositoryProcessor --> RefactorActivity : executes
    RepositoryProcessor --> TestActivity : executes
    CompliancePipeline --> ReportActivity : executes
    CompliancePipeline --> CostEstimationActivity : executes
```

### 2.4 Agent and Tool Layer (`agents/`, `tools/`)

```mermaid
classDiagram
    class GitClient {
        -Optional~str~ _token
        -Path _work_dir
        +clone(url: str, path: Path, depth: int) void
        +create_branch(repo: Path, name: str) void
        +checkout(repo: Path, branch: str) void
        +add(repo: Path, files: list~str~) void
        +commit(repo: Path, message: str) str
        +push(repo: Path, remote: str, branch: str) void
        +diff(repo: Path, staged: bool) str
        +log(repo: Path, n: int) list~CommitInfo~
        -_run(args: list~str~, cwd: Path) CompletedProcess
        -_acquire_token(url: str) str
    }

    class GitProviderClient {
        <<abstract>>
        +create_pull_request(repo: str, branch: str, title: str, body: str) str
        +add_comment(repo: str, pr_number: int, body: str) void
        +get_pr_status(repo: str, pr_number: int) PRStatus
    }

    class GitHubClient {
        -httpx.AsyncClient _client
        -str _app_id
        +create_pull_request(...) str
        +add_comment(...) void
        +get_pr_status(...) PRStatus
        -_get_installation_token() str
    }

    class GitLabClient {
        -httpx.AsyncClient _client
        +create_pull_request(...) str
        +add_comment(...) void
    }

    class ASTEngine {
        -dict~str,Language~ _languages
        -dict~str,Parser~ _parsers
        +parse(source: str, language: str) Tree
        +query(tree: Tree, query_str: str) list~Match~
        +find_classes(tree: Tree) list~ClassNode~
        +find_annotations(tree: Tree, class_node: ClassNode) list~str~
        +find_methods(tree: Tree, class_node: ClassNode) list~str~
        +get_node_range(node: Node) ASTRegion
        +check_implements(tree: Tree, class_node: ClassNode, interface: str) bool
        -_get_parser(language: str) Parser
        -_detect_language(file_path: str) str
    }

    class TemplateEngine {
        -SandboxedEnvironment _env
        +render(template_path: Path, context: dict) str
        +render_string(template_str: str, context: dict) str
        +validate_template(template_path: Path) list~str~
        -_create_sandboxed_env() SandboxedEnvironment
    }

    class TestRunner {
        +execute(test_files: list~Path~, repo: Path, timeout: int) TestResult
        -_build_sandbox_command(test_files: list~Path~) list~str~
        -_parse_test_output(stdout: str, stderr: str) TestResult
        -_validate_no_network() void
        -_apply_resource_limits() dict
    }

    class SearchClient {
        -AsyncElasticsearch _client
        +index_regulation(plugin: RegulationPlugin) void
        +search_rules(query: str, regulation_id: Optional~str~) list~RuleSearchResult~
        +search_context(query: str) list~DocumentChunk~
        -_build_query(query: str, filters: dict) dict
    }

    GitProviderClient <|-- GitHubClient
    GitProviderClient <|-- GitLabClient
```

### 2.5 Repository Layer (`repositories/`)

```mermaid
classDiagram
    class BaseRepository {
        #AsyncConnectionPool _pool
        +__init__(pool: AsyncConnectionPool)
        #_fetch_one(query: str, params: tuple) Optional~Row~
        #_fetch_all(query: str, params: tuple) list~Row~
        #_execute(query: str, params: tuple) void
    }

    class PipelineRunRepository {
        +create(regulation_id: str, total_repos: int, config: dict) UUID
        +update_status(run_id: UUID, status: str) void
        +update_cost(run_id: UUID, actual_cost: float) void
        +complete(run_id: UUID, status: str) void
        +get(run_id: UUID) Optional~PipelineRun~
        +list_by_status(status: str) list~PipelineRun~
        +list_by_regulation(regulation_id: str) list~PipelineRun~
    }

    class RepositoryProgressRepository {
        +create(run_id: UUID, repo_url: str) UUID
        +update_status(id: UUID, status: str, branch: Optional~str~, sha: Optional~str~) void
        +set_pr_url(id: UUID, pr_url: str) void
        +set_error(id: UUID, error: str) void
        +get_by_run(run_id: UUID) list~RepositoryProgress~
        +get_failed(run_id: UUID) list~RepositoryProgress~
        +count_by_status(run_id: UUID) dict~str,int~
    }

    class AuditRepository {
        +insert(entry: AuditEntry) void
        +bulk_insert(entries: list~AuditEntry~) void
        +get_by_run(run_id: UUID) list~AuditEntry~
        +get_by_type(run_id: UUID, event_type: str) list~AuditEntry~
        +get_by_date_range(start: datetime, end: datetime) list~AuditEntry~
        +export_partition(year: int, month: int, output: Path) void
    }

    class CheckpointDecisionRepository {
        +create(run_id: UUID, decision: CheckpointDecision) UUID
        +get_by_run(run_id: UUID) list~CheckpointDecision~
        +get_latest(run_id: UUID, checkpoint_type: str) Optional~CheckpointDecision~
    }

    class ConflictLogRepository {
        +create(run_id: UUID, conflict: ConflictRecord) UUID
        +resolve(id: UUID, resolution: str, decision_id: UUID) void
        +get_by_run(run_id: UUID) list~ConflictLogEntry~
        +get_unresolved(run_id: UUID) list~ConflictLogEntry~
    }

    BaseRepository <|-- PipelineRunRepository
    BaseRepository <|-- RepositoryProgressRepository
    BaseRepository <|-- AuditRepository
    BaseRepository <|-- CheckpointDecisionRepository
    BaseRepository <|-- ConflictLogRepository
```

### 2.6 Event System (`events/`)

```mermaid
classDiagram
    class EventSource {
        <<protocol>>
        +start() void*
        +stop() void*
    }

    class KafkaEventSource {
        -Consumer _consumer
        -str _topic
        -str _group_id
        -WorkflowStarter _starter
        +start() void
        +stop() void
        -_consume_loop() void
        -_deserialize(message: Message) RegulatoryEvent
        -_handle_error(error: KafkaError) void
    }

    class WebhookEventSource {
        -FastAPI _app
        -WorkflowStarter _starter
        +start() void
        +stop() void
        +handle_event(request: Request) Response
        -_validate_hmac(request: Request) bool
    }

    class SQSEventSource {
        -boto3.Client _sqs
        -str _queue_url
        -WorkflowStarter _starter
        +start() void
        +stop() void
        -_poll_loop() void
        -_delete_message(receipt_handle: str) void
    }

    class FileEventSource {
        -Path _watch_dir
        -WorkflowStarter _starter
        +start() void
        +stop() void
        -_watch_loop() void
        -_process_file(path: Path) void
    }

    class WorkflowStarter {
        -TemporalClient _client
        -str _task_queue
        +start_pipeline(event: RegulatoryEvent) str
        +signal_approval(workflow_id: str, decision: CheckpointDecision) void
        +query_status(workflow_id: str) PipelineStatus
        +cancel(workflow_id: str) void
        +list_running() list~WorkflowInfo~
    }

    EventSource <|.. KafkaEventSource
    EventSource <|.. WebhookEventSource
    EventSource <|.. SQSEventSource
    EventSource <|.. FileEventSource
    KafkaEventSource --> WorkflowStarter
    WebhookEventSource --> WorkflowStarter
    SQSEventSource --> WorkflowStarter
    FileEventSource --> WorkflowStarter
```

### 2.7 Observability (`observability/`)

```mermaid
classDiagram
    class AuditSigner {
        -Ed25519PrivateKey _private_key
        -Ed25519PublicKey _public_key
        +sign(payload: dict) str
        +verify(payload: dict, signature: str) bool
        +load_key(path: Path) void
        +generate_key_pair() tuple~bytes,bytes~
        -_canonicalize(payload: dict) bytes
    }

    class ObservabilitySetup {
        +configure_mlflow(tracking_uri: str) void
        +configure_otel(temporal_client: Client) TracingInterceptor
        +configure_audit_signer(key_path: Path) AuditSigner
        -_setup_pydanticai_autolog() void
        -_setup_litellm_callbacks() void
        -_setup_otel_exporter(endpoint: str) void
    }

    class AuditLogger {
        -AuditRepository _repo
        -AuditSigner _signer
        +log_llm_call(run_id: UUID, model: str, prompt: str, response: str, tokens: int, cost: float) void
        +log_tool_invocation(run_id: UUID, tool: str, input: dict, output: dict) void
        +log_state_transition(run_id: UUID, from_state: str, to_state: str, trigger: str) void
        +log_human_decision(run_id: UUID, decision: CheckpointDecision) void
        +log_conflict_detected(run_id: UUID, conflict: ConflictRecord) void
        -_create_entry(run_id: UUID, event_type: str, payload: dict) AuditEntry
    }

    ObservabilitySetup --> AuditSigner
    AuditLogger --> AuditRepository
    AuditLogger --> AuditSigner
```

---

## 3. Detailed Sequence Diagrams

### 3.1 Plugin Loading and Validation

```mermaid
sequenceDiagram
    participant CLI as rak CLI
    participant PL as PluginLoader
    participant YAML as ruamel.yaml
    participant PY as Pydantic v2
    participant DSL as ConditionDSL
    participant TE as TemplateEngine
    participant FS as Filesystem

    CLI->>PL: load(path="regulations/dora/dora-ict-risk-2025.yaml")
    PL->>FS: Read YAML file
    FS-->>PL: Raw bytes
    PL->>YAML: parse(bytes)
    YAML-->>PL: dict (preserving comments, ordering)
    PL->>PY: RegulationPlugin.model_validate(dict)

    Note over PY: Pydantic validates:<br/>- Required fields (id, name, disclaimer, ...)<br/>- Type coercion (date, HttpUrl, Literal)<br/>- model_extra captures unknown fields

    alt Validation fails
        PY-->>PL: ValidationError (field, message, loc)
        PL-->>CLI: list[ValidationError]
    else Validation succeeds
        PY-->>PL: RegulationPlugin instance

        loop For each rule in plugin.rules
            loop For each affects clause
                PL->>DSL: parse(condition)
                DSL-->>PL: ConditionAST

                alt Parse error
                    DSL-->>PL: SyntaxError(line, col, message)
                    PL->>PL: Collect error
                end
            end

            PL->>FS: Check template exists (remediation.template)
            alt Template missing
                PL->>PL: Collect error: "Template not found: {path}"
            else Template exists
                PL->>TE: validate_template(path)
                TE-->>PL: list[str] (template syntax errors)
            end
        end

        PL-->>CLI: RegulationPlugin (or errors)
    end
```

### 3.2 Analyzer Agent — Rule Matching for a Single File

```mermaid
sequenceDiagram
    participant ACT as AnalyzeActivity
    participant AGENT as AnalyzerAgent<br/>(PydanticAI)
    participant AST as ASTEngine<br/>(tree-sitter)
    participant DSL as ConditionDSL
    participant LLM as LiteLLM
    participant MLF as MLflow
    participant ES as Elasticsearch

    ACT->>ACT: For each file matching rule.affects.pattern (glob)

    ACT->>AST: parse(file_content, language="java")
    AST-->>ACT: Tree (AST)

    ACT->>AST: find_classes(tree)
    AST-->>ACT: [ClassNode("UserService"), ClassNode("PaymentGateway")]

    loop For each class_node
        loop For each rule in plugin.rules
            ACT->>DSL: parse(rule.affects.condition)
            DSL-->>ACT: ConditionAST

            ACT->>DSL: can_evaluate_statically(ast)

            alt Static evaluation possible
                Note over ACT,AST: Example: "class implements ICTService<br/>AND NOT has_annotation(@AuditLog)"

                ACT->>AST: check_implements(tree, class_node, "ICTService")
                AST-->>ACT: true

                ACT->>AST: find_annotations(tree, class_node)
                AST-->>ACT: ["@Service", "@Transactional"]
                Note over ACT: @AuditLog NOT found -> condition matches

                ACT->>ACT: Create RuleMatch(rule_id, confidence=1.0)

            else Requires LLM (semantic condition)
                Note over ACT,LLM: Example: "method handles payment<br/>AND NOT logs transaction ID"

                ACT->>DSL: to_llm_prompt(ast)
                DSL-->>ACT: "Does this class handle payment processing AND does it fail to log transaction IDs?"

                ACT->>ES: search_context(rule.description)
                ES-->>ACT: Regulatory context chunks

                ACT->>AGENT: run(file_content + prompt + context)
                AGENT->>LLM: Structured output request (result_type=RuleMatch)
                LLM-->>MLF: Trace (automatic callback)
                LLM-->>AGENT: JSON {matched: true, confidence: 0.78, reasoning: "..."}
                AGENT-->>ACT: RuleMatch(rule_id, confidence=0.78)
            end
        end
    end

    ACT->>ACT: Aggregate all RuleMatches -> FileImpact
```

### 3.3 Refactor Agent — Applying a Remediation Template

```mermaid
sequenceDiagram
    participant ACT as RefactorActivity
    participant GIT as GitClient
    participant AST as ASTEngine
    participant TE as TemplateEngine
    participant AGENT as RefactorAgent<br/>(PydanticAI)
    participant LLM as LiteLLM
    participant AL as AuditLogger

    ACT->>GIT: create_branch(repo, "rak/dora-ict-risk/DORA-ICT-001")
    GIT-->>ACT: Branch created

    loop For each FileImpact in impact_map
        loop For each RuleMatch in file_impact
            ACT->>ACT: Load remediation strategy from rule

            alt Strategy: add_annotation
                ACT->>AST: parse(file_content, language)
                AST-->>ACT: Tree
                ACT->>AST: find_classes(tree) -> target class node
                ACT->>AST: get_node_range(class_node)
                AST-->>ACT: ASTRegion(start_line=15, ...)

                ACT->>TE: render(template, {class_name, package, rule_id, ...})
                TE-->>ACT: Rendered annotation code

                ACT->>ACT: Insert annotation at line 15

            else Strategy: add_configuration
                ACT->>TE: render(template, {service_name, rto, rpo, ...})
                TE-->>ACT: Rendered YAML fragment
                ACT->>ACT: Merge fragment into target YAML

            else Strategy: replace_pattern
                ACT->>TE: render(template, {old_pattern, new_pattern, ...})
                TE-->>ACT: Rendered replacement
                ACT->>AST: query(tree, old_pattern_query)
                AST-->>ACT: Matching nodes
                ACT->>ACT: Replace each match

            else Strategy: custom_agent
                ACT->>AGENT: run(file_content, rule, remediation_config)
                AGENT->>LLM: Generate remediation
                LLM-->>AGENT: Modified code
                AGENT-->>ACT: Modified code + confidence

            end

            ACT->>ACT: compute_confidence(original, modified)
            ACT->>GIT: add(repo, [modified_file])
        end
    end

    ACT->>GIT: commit(repo, "rak: DORA-ICT-001 remediation")
    GIT-->>ACT: commit_sha

    ACT->>AL: log_tool_invocation(run_id, "refactor", input, output)
    ACT-->>ACT: Return ChangeSet
```

### 3.4 Human Checkpoint — Approval Flow

```mermaid
sequenceDiagram
    participant WF as CompliancePipeline<br/>(Temporal Workflow)
    participant TS as Temporal Server
    participant PG as PostgreSQL
    participant API as FastAPI
    participant NOTIF as Slack / Email
    participant HUMAN as Tech Lead
    participant SIGNER as AuditSigner

    Note over WF: Analysis complete. Impact map produced.

    WF->>NOTIF: Send notification with impact summary
    NOTIF-->>HUMAN: "Impact review ready for run abc-123"
    WF->>WF: await workflow.wait_condition(<br/>  lambda: self.impact_review_decision is not None<br/>)

    Note over TS: Workflow is durably paused.<br/>State persisted to PostgreSQL.<br/>Worker can be restarted.

    HUMAN->>HUMAN: Reviews impact map (via Temporal UI, Slack, or custom UI)

    HUMAN->>API: POST /approvals/abc-123<br/>{decision: "approved", rationale: "LGTM", actor: "jane@corp.com"}

    API->>API: Validate request (Pydantic)
    API->>SIGNER: sign(payload)
    SIGNER-->>API: Ed25519 signature

    API->>PG: INSERT checkpoint_decisions<br/>{run_id, actor, decision, rationale, signature}

    API->>TS: temporal_client.get_workflow_handle("abc-123")<br/>.signal(approve_impact_review, decision)

    TS->>WF: Deliver signal
    WF->>WF: self.impact_review_decision = decision
    WF->>WF: wait_condition satisfied -> resume

    alt Decision: approved
        WF->>WF: Proceed to REFACTORING
    else Decision: rejected
        WF->>WF: Return PipelineResult(status="rejected")
    else Decision: modifications_requested
        WF->>WF: Re-enter analysis with feedback
    end
```

### 3.5 Test Execution — Sandboxed

```mermaid
sequenceDiagram
    participant ACT as TestActivity
    participant AGENT as TestGeneratorAgent
    participant LLM as LiteLLM
    participant AST as ASTEngine
    participant TR as TestRunner
    participant DOCKER as Docker Engine
    participant AL as AuditLogger

    ACT->>AGENT: Generate tests for ChangeSet
    AGENT->>LLM: Generate compliance + regression tests
    LLM-->>AGENT: Test code (structured output)
    AGENT-->>ACT: list[test_files]

    ACT->>AST: parse(each test file)
    Note over ACT,AST: Static analysis:<br/>- No import os/subprocess/socket<br/>- No file writes outside test dir<br/>- No network calls<br/>- No env var access

    alt Suspicious patterns found
        ACT->>ACT: Reject test file, log warning
    else Clean
        ACT->>TR: execute(test_files, repo, timeout=300)

        TR->>DOCKER: docker run \<br/>  --network=none \<br/>  --read-only \<br/>  --memory=512m \<br/>  --cpus=1 \<br/>  --tmpfs /tmp:size=100m \<br/>  --timeout=300s \<br/>  python:3.12-slim \<br/>  pytest test_files

        Note over DOCKER: Container has:<br/>- No network access<br/>- Read-only filesystem<br/>- 512MB memory limit<br/>- 1 CPU limit<br/>- 300s timeout<br/>- Writable /tmp (100MB)

        DOCKER-->>TR: stdout, stderr, exit_code

        TR->>TR: parse_test_output(stdout, stderr)
        TR-->>ACT: TestResult {pass_rate, failures}
    end

    ACT->>AL: log_tool_invocation(run_id, "test_execution", ...)
```

---

## 4. State Machine Diagrams

### 4.1 Pipeline Run Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING : Workflow started

    PENDING --> COST_ESTIMATION : Estimating LLM cost

    COST_ESTIMATION --> ANALYZING : Cost within threshold
    COST_ESTIMATION --> COST_REJECTED : Cost exceeds threshold
    COST_ESTIMATION --> FAILED : Estimation error

    ANALYZING --> AWAITING_IMPACT_REVIEW : Analysis complete
    ANALYZING --> FAILED : Agent/tool failure

    AWAITING_IMPACT_REVIEW --> REFACTORING : Human approves
    AWAITING_IMPACT_REVIEW --> REJECTED : Human rejects (false positive)
    AWAITING_IMPACT_REVIEW --> ANALYZING : Human requests re-analysis

    REFACTORING --> TESTING : Changes committed
    REFACTORING --> FAILED : Agent/tool failure

    TESTING --> AWAITING_MERGE_REVIEW : All tests pass
    TESTING --> REFACTORING : Tests fail (retry, max 3)
    TESTING --> FAILED : Max retries exceeded

    AWAITING_MERGE_REVIEW --> REPORTING : Human approves
    AWAITING_MERGE_REVIEW --> REFACTORING : Human requests modifications
    AWAITING_MERGE_REVIEW --> REJECTED : Human rejects

    REPORTING --> COMPLETED : Reports + PRs delivered
    REPORTING --> FAILED : Reporting error

    COMPLETED --> [*]
    FAILED --> [*]
    REJECTED --> [*]
    COST_REJECTED --> [*]
    CANCELLED --> [*]

    PENDING --> CANCELLED : Operator cancels
    COST_ESTIMATION --> CANCELLED : Operator cancels
    ANALYZING --> CANCELLED : Operator cancels
    AWAITING_IMPACT_REVIEW --> CANCELLED : Operator cancels
    REFACTORING --> CANCELLED : Operator cancels
    TESTING --> CANCELLED : Operator cancels
    AWAITING_MERGE_REVIEW --> CANCELLED : Operator cancels

    note right of AWAITING_IMPACT_REVIEW
        Temporal Signal gate.
        Workflow durably paused.
        Non-bypassable.
    end note

    note right of AWAITING_MERGE_REVIEW
        Temporal Signal gate.
        Workflow durably paused.
        Non-bypassable.
    end note
```

#### 4.1.1 Workflow Phase vs. Database Status

The state machine above represents the **Temporal workflow phase** — the granular orchestration state managed by Temporal's event-sourced history. The `pipeline_runs.status` column in PostgreSQL tracks a **coarse lifecycle status** for dashboard queries and reporting. These are two distinct state representations by design: Temporal is the authority for which phase is active, PostgreSQL is the authority for lifecycle queries.

**Mapping: DB `status` → Temporal workflow phases**

| DB `pipeline_runs.status` | Temporal Workflow Phases Covered | Semantics |
|---|---|---|
| `pending` | `PENDING` | Workflow created, not yet started |
| `running` | `COST_ESTIMATION`, `ANALYZING`, `AWAITING_IMPACT_REVIEW`, `REFACTORING`, `TESTING`, `AWAITING_MERGE_REVIEW`, `REPORTING` | Pipeline is actively executing (any intermediate phase) |
| `cost_rejected` | `COST_REJECTED` | Cost estimate exceeded threshold; operator rejected |
| `completed` | `COMPLETED` | All outputs delivered successfully |
| `failed` | `FAILED` (from any phase) | Unrecoverable error after retry exhaustion |
| `rejected` | `REJECTED` | Human rejected at a checkpoint |
| `cancelled` | `CANCELLED` | Operator-initiated cancellation via Temporal API |

**Implications for `rak status`:** The CLI queries both sources — `pipeline_runs.status` for the lifecycle state, and the Temporal API (`workflow.describe()`) for the current phase — to display a complete picture. Example output:

```
Run:    a1b2c3d4-...
Status: running
Phase:  AWAITING_IMPACT_REVIEW (waiting for human approval)
Repos:  12 pending, 3 in_progress, 5 completed, 0 failed
Cost:   $4.20 / $10.00 estimated
```

### 4.2 Repository Progress Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING : Repository registered for run

    PENDING --> IN_PROGRESS : Worker starts processing

    IN_PROGRESS --> COMPLETED : All phases pass + PR created
    IN_PROGRESS --> FAILED : Unrecoverable error
    IN_PROGRESS --> SKIPPED : No matching rules (not affected)

    FAILED --> IN_PROGRESS : rak retry-failures (re-dispatch)

    COMPLETED --> [*]
    FAILED --> [*]
    SKIPPED --> [*]
```

### 4.3 Condition DSL Evaluation

```mermaid
stateDiagram-v2
    [*] --> PARSE : Input condition string

    PARSE --> TOKENIZE : Split by AND/OR/NOT/predicates
    TOKENIZE --> BUILD_AST : Construct ConditionAST tree

    BUILD_AST --> CLASSIFY : For each leaf predicate

    CLASSIFY --> STATIC_EVAL : Predicate is AST-checkable
    CLASSIFY --> LLM_EVAL : Predicate is semantic

    STATIC_EVAL --> RESULT : tree-sitter query
    LLM_EVAL --> RESULT : LLM call with prompt

    RESULT --> COMBINE : Evaluate AND/OR/NOT logic
    COMBINE --> MATCHED : Final result = true
    COMBINE --> NOT_MATCHED : Final result = false

    MATCHED --> [*]
    NOT_MATCHED --> [*]

    note right of CLASSIFY
        Static: implements, inherits,
        has_annotation, has_decorator,
        has_method, has_key, matches

        Semantic: Any condition that
        requires understanding intent
    end note
```

### 4.4 Audit Entry Lifecycle

```mermaid
stateDiagram-v2
    [*] --> CREATED : Event occurs (LLM call, tool use, decision)

    CREATED --> SIGNED : AuditSigner.sign(payload)
    Note right of SIGNED: Ed25519 signature<br/>over canonicalized JSON

    SIGNED --> PERSISTED : INSERT into rak.audit_entries
    Note right of PERSISTED: Append-only table.<br/>No UPDATE/DELETE grants.

    PERSISTED --> REPLICATED : Monthly partition export to S3
    Note right of REPLICATED: Parquet or JSON-LD format.<br/>Versioned S3 bucket.

    REPLICATED --> [*]

    Note left of CREATED: Entries are never modified<br/>after creation. The signature<br/>makes tampering detectable.
```

---

## 5. Database Schema Details

> **Cross-reference:** The canonical data dictionary, indexing strategy, JSONB payload schemas, Elasticsearch mappings, partitioning/retention policies, and migration plan are in [`data-model.md`](data-model.md). The DDL below focuses on constraints, indexes, roles, and security grants relevant to code-level implementation.

### 5.1 Complete DDL with Constraints, Indexes, and Security

```sql
-- ============================================================
-- Schema: rak
-- Managed by: Alembic migrations
-- Owner: rak_admin role
-- Application access: rak_app role
-- ============================================================

CREATE SCHEMA IF NOT EXISTS rak;

-- Roles
CREATE ROLE rak_admin;
CREATE ROLE rak_app;

-- --------------------------------------------------------
-- Table: pipeline_runs
-- --------------------------------------------------------
CREATE TABLE rak.pipeline_runs (
    run_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    regulation_id   TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','running','cost_rejected',
                                    'completed','failed','rejected','cancelled')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    total_repos     INTEGER     NOT NULL CHECK (total_repos > 0),
    estimated_cost  NUMERIC(10,4),
    actual_cost     NUMERIC(10,4) DEFAULT 0,
    config_snapshot JSONB       NOT NULL,

    -- Temporal workflow ID for cross-referencing
    temporal_workflow_id TEXT   UNIQUE,

    CONSTRAINT valid_completion CHECK (
        (status IN ('completed','failed','rejected','cancelled') AND completed_at IS NOT NULL)
        OR (status NOT IN ('completed','failed','rejected','cancelled') AND completed_at IS NULL)
    )
);

CREATE INDEX idx_runs_status      ON rak.pipeline_runs (status);
CREATE INDEX idx_runs_regulation  ON rak.pipeline_runs (regulation_id);
CREATE INDEX idx_runs_created     ON rak.pipeline_runs (created_at DESC);

-- --------------------------------------------------------
-- Table: repository_progress
-- --------------------------------------------------------
CREATE TABLE rak.repository_progress (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      UUID        NOT NULL REFERENCES rak.pipeline_runs(run_id)
                            ON DELETE CASCADE,
    repo_url    TEXT        NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','in_progress','completed',
                                'failed','skipped')),
    branch_name TEXT,
    commit_sha  CHAR(40),   -- SHA-1 hash, always 40 chars
    pr_url      TEXT,
    error       TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (run_id, repo_url),

    -- If status is 'completed' or 'in_progress', branch_name must be set.
    CONSTRAINT branch_when_active CHECK (
        status NOT IN ('completed','in_progress')
        OR branch_name IS NOT NULL
    )
);

CREATE INDEX idx_progress_run    ON rak.repository_progress (run_id);
CREATE INDEX idx_progress_status ON rak.repository_progress (status);

-- Trigger: auto-update updated_at
CREATE OR REPLACE FUNCTION rak.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_progress_updated
    BEFORE UPDATE ON rak.repository_progress
    FOR EACH ROW EXECUTE FUNCTION rak.update_timestamp();

-- --------------------------------------------------------
-- Table: audit_entries (partitioned, append-only)
-- --------------------------------------------------------
CREATE TABLE rak.audit_entries (
    entry_id    UUID        NOT NULL DEFAULT gen_random_uuid(),
    -- NOTE: run_id is NOT a foreign key to pipeline_runs.
    -- PostgreSQL does not support FK constraints on partitioned tables
    -- referencing non-partitioned tables. Application code validates
    -- run_id existence before insert. See data-model.md for details.
    run_id      UUID        NOT NULL,
    event_type  TEXT        NOT NULL
                CHECK (event_type IN ('llm_call','tool_invocation',
                    'state_transition','human_decision','conflict_detected',
                    'cost_estimation','test_execution','merge_request',
                    'error')),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload     JSONB       NOT NULL,
    signature   TEXT        NOT NULL,  -- Ed25519 base64-encoded signature

    PRIMARY KEY (timestamp, entry_id)
) PARTITION BY RANGE (timestamp);

-- Pre-create partitions for current and next months
-- (automated via pg_partman in production)
CREATE TABLE rak.audit_entries_2026_03 PARTITION OF rak.audit_entries
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE rak.audit_entries_2026_04 PARTITION OF rak.audit_entries
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE INDEX idx_audit_run     ON rak.audit_entries (run_id);
CREATE INDEX idx_audit_type    ON rak.audit_entries (event_type);
CREATE INDEX idx_audit_payload ON rak.audit_entries USING GIN (payload);

-- Expression index for common JSON queries
CREATE INDEX idx_audit_model ON rak.audit_entries ((payload->>'model'))
    WHERE event_type = 'llm_call';

-- --------------------------------------------------------
-- Table: checkpoint_decisions
-- --------------------------------------------------------
CREATE TABLE rak.checkpoint_decisions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID        NOT NULL REFERENCES rak.pipeline_runs(run_id)
                                ON DELETE CASCADE,
    checkpoint_type TEXT        NOT NULL
                    CHECK (checkpoint_type IN ('impact_review','merge_review')),
    actor           TEXT        NOT NULL,
    decision        TEXT        NOT NULL
                    CHECK (decision IN ('approved','rejected','modifications_requested')),
    rationale       TEXT,
    signature       TEXT        NOT NULL,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Multiple decisions per checkpoint type are allowed (re-reviews).
    -- Each re-review creates a new row with a different decided_at.
    -- The application queries the latest decision per checkpoint type:
    --   SELECT DISTINCT ON (checkpoint_type) * FROM checkpoint_decisions
    --   WHERE run_id = $1 ORDER BY checkpoint_type, decided_at DESC;
    -- This preserves the full audit trail of all approval/rejection decisions.
    UNIQUE (run_id, checkpoint_type, decided_at)
);

CREATE INDEX idx_checkpoint_run ON rak.checkpoint_decisions (run_id);

-- --------------------------------------------------------
-- Table: conflict_log
-- --------------------------------------------------------
CREATE TABLE rak.conflict_log (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id            UUID        NOT NULL REFERENCES rak.pipeline_runs(run_id)
                                  ON DELETE CASCADE,
    conflicting_rules JSONB       NOT NULL,  -- [{regulation_id, rule_id}, ...]
    affected_regions  JSONB       NOT NULL,  -- [{file, start_line, end_line}, ...]
    resolution        TEXT,
    human_decision_id UUID        REFERENCES rak.checkpoint_decisions(id),
    detected_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT resolution_needs_decision CHECK (
        (resolution IS NOT NULL AND human_decision_id IS NOT NULL)
        OR resolution IS NULL
    )
);

CREATE INDEX idx_conflict_run ON rak.conflict_log (run_id);

-- --------------------------------------------------------
-- Table: file_analysis_cache
-- --------------------------------------------------------
CREATE TABLE rak.file_analysis_cache (
    cache_key   CHAR(64)    PRIMARY KEY,  -- SHA256(content + plugin_version + agent_version)
    repo_url    TEXT        NOT NULL,
    file_path   TEXT        NOT NULL,
    result      JSONB       NOT NULL,     -- Cached ImpactMap for this file
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '7 days'
);

CREATE INDEX idx_cache_expires ON rak.file_analysis_cache (expires_at);

-- --------------------------------------------------------
-- Access Control
-- --------------------------------------------------------
GRANT USAGE ON SCHEMA rak TO rak_app;

-- Full access to most tables
GRANT SELECT, INSERT, UPDATE ON rak.pipeline_runs TO rak_app;
GRANT SELECT, INSERT, UPDATE ON rak.repository_progress TO rak_app;
GRANT SELECT, INSERT ON rak.checkpoint_decisions TO rak_app;
GRANT SELECT, INSERT, UPDATE ON rak.conflict_log TO rak_app;
GRANT SELECT, INSERT, DELETE ON rak.file_analysis_cache TO rak_app;

-- AUDIT TABLE: INSERT + SELECT ONLY (append-only enforcement)
GRANT SELECT, INSERT ON rak.audit_entries TO rak_app;
-- NO UPDATE, NO DELETE on audit_entries for rak_app

-- Admin has full access (for partition management, exports)
GRANT ALL ON ALL TABLES IN SCHEMA rak TO rak_admin;
```

### 5.2 Audit Entry Payload Schemas (JSON-LD)

Each `event_type` has a specific `payload` structure:

```json
// event_type: "llm_call"
{
  "@context": "https://schema.org",
  "@type": "LLMCall",
  "model": "anthropic/claude-sonnet-4-6",
  "model_version": "claude-sonnet-4-6-20260327",
  "prompt_hash": "sha256:abc...",
  "prompt_tokens": 4200,
  "completion_tokens": 1800,
  "total_tokens": 6000,
  "latency_ms": 3400,
  "cost_usd": 0.042,
  "temperature": 0.0,
  "agent": "analyzer",
  "purpose": "evaluate_condition",
  "rule_id": "DORA-ICT-001",
  "file_path": "src/main/java/com/example/UserService.java",
  "confidence": 0.92
}

// event_type: "human_decision"
{
  "@context": "https://schema.org",
  "@type": "HumanDecision",
  "checkpoint_type": "impact_review",
  "actor": "jane@corp.com",
  "decision": "approved",
  "rationale": "Impact assessment looks correct. Proceed with remediation.",
  "repos_affected": 42,
  "rules_matched": ["DORA-ICT-001", "DORA-ICT-002"]
}

// event_type: "state_transition"
{
  "@context": "https://schema.org",
  "@type": "StateTransition",
  "from_state": "ANALYZING",
  "to_state": "AWAITING_IMPACT_REVIEW",
  "trigger": "analysis_complete",
  "repos_analyzed": 42,
  "files_impacted": 156,
  "conflicts_detected": 2
}
```

---

## 6. Algorithms and Business Logic

### 6.1 Condition DSL Parser

The Condition DSL parses predicate expressions into an AST for evaluation against tree-sitter parse trees.

**Grammar (EBNF):**

```
expression  = or_expr
or_expr     = and_expr ( "OR" and_expr )*
and_expr    = not_expr ( "AND" not_expr )*
not_expr    = "NOT" not_expr | primary
primary     = predicate | "(" expression ")"
predicate   = class_pred | annotation_pred | method_pred | key_pred | match_pred
class_pred  = "class" ("implements" | "inherits") IDENTIFIER
annotation_pred = ("has_annotation" | "has_decorator") "(" "@" IDENTIFIER ")"
method_pred = "has_method" "(" IDENTIFIER ")"
key_pred    = "has_key" "(" DOTTED_PATH ")"
match_pred  = "class_name" "matches" QUOTED_STRING
```

**Parsing algorithm (recursive descent):**

```python
def parse(expression: str) -> ConditionAST:
    tokens = tokenize(expression)
    pos = 0

    def parse_or() -> ConditionAST:
        left = parse_and()
        while current_token() == "OR":
            consume("OR")
            right = parse_and()
            left = ConditionAST(node_type="OR", children=[left, right])
        return left

    def parse_and() -> ConditionAST:
        left = parse_not()
        while current_token() == "AND":
            consume("AND")
            right = parse_not()
            left = ConditionAST(node_type="AND", children=[left, right])
        return left

    def parse_not() -> ConditionAST:
        if current_token() == "NOT":
            consume("NOT")
            child = parse_not()
            return ConditionAST(node_type="NOT", children=[child])
        return parse_primary()

    def parse_primary() -> ConditionAST:
        if current_token() == "(":
            consume("(")
            expr = parse_or()
            consume(")")
            return expr
        return parse_predicate()

    def parse_predicate() -> ConditionAST:
        # Dispatch to specific predicate parsers
        # Returns ConditionAST(node_type="PREDICATE", predicate=Predicate(...))
        ...

    return parse_or()
```

**Operator Precedence (highest to lowest):**

| Precedence | Operator | Associativity | Example |
|---|---|---|---|
| 1 (highest) | `NOT` | Right | `NOT has_annotation(@Foo)` |
| 2 | `AND` | Left | `A AND B AND C` → `(A AND B) AND C` |
| 3 (lowest) | `OR` | Left | `A OR B OR C` → `(A OR B) OR C` |

Parentheses override precedence: `A OR (B AND NOT C)`.

**Static vs. LLM Evaluation:**

Each leaf predicate is classified as statically evaluable or requiring LLM delegation:

| Predicate | Evaluation | Method | Confidence |
|---|---|---|---|
| `class implements X` | **Static** | tree-sitter query for class inheritance | 1.0 |
| `class inherits X` | **Static** | tree-sitter query for class hierarchy | 1.0 |
| `has_annotation(@X)` | **Static** | tree-sitter query for decorator/annotation nodes | 1.0 |
| `has_decorator(@X)` | **Static** | tree-sitter query for decorator nodes (Python) | 1.0 |
| `has_method(X)` | **Static** | tree-sitter query for method definitions | 1.0 |
| `has_key(X.Y.Z)` | **Static** | YAML/JSON key path lookup | 1.0 |
| `class_name matches "regex"` | **Static** | Regex match on class name node text | 1.0 |
| Semantic conditions | **LLM** | `to_llm_prompt()` generates a constrained prompt | 0.6–0.9 (model-dependent) |

**LLM Delegation for Semantic Conditions:**

When `can_evaluate_statically()` returns `False` for a predicate (e.g., a condition requiring understanding of business intent), the `to_llm_prompt()` method converts the condition AST into a constrained LLM prompt:

```python
def to_llm_prompt(self, ast: ConditionAST) -> str:
    """Convert a non-static condition into an LLM evaluation prompt."""
    # 1. Serialize the condition as natural language
    # 2. Include the file content as context
    # 3. Constrain the output to a Pydantic schema:
    #    class ConditionResult(BaseModel):
    #        matches: bool
    #        confidence: float  # 0.0–1.0
    #        reasoning: str     # explanation for audit trail
    # 4. The PydanticAI agent enforces structured output
    ...
```

The LLM evaluation result includes a confidence score. If `confidence < rule.remediation.confidence_threshold`, the match is flagged for additional human review at the next checkpoint.

**Boolean Combination:**

After all leaf predicates are evaluated (statically or via LLM), the boolean operators combine results bottom-up through the AST. Confidence for combined expressions uses minimum propagation: `AND` takes the minimum confidence of its children, `OR` takes the maximum, and `NOT` preserves the child's confidence.

### 6.2 Cross-Regulation Conflict Detection

```python
def detect_conflicts(
    plugins: list[RegulationPlugin],
    impact_maps: dict[str, ImpactMap],   # keyed by plugin.id
) -> list[ConflictRecord]:
    """
    Detects when two regulation plugins produce conflicting remediations
    for overlapping code regions.

    Algorithm:
    1. Build a spatial index of all affected AST regions per file
    2. For each file, find all pairs of (plugin_A.rule, plugin_B.rule)
       where the affected AST regions overlap
    3. For each overlapping pair, check the cross_reference relationship
    4. If relationship is "takes_precedence", suppress the lower-priority rule
    5. If relationship is "does_not_override" and remediation strategies conflict,
       create a ConflictRecord and escalate to human

    Complexity: O(P^2 * F * R) where P=plugins, F=files, R=rules per file
    In practice: P < 5, F < 100 affected files, R < 10 rules per file
    """
    conflicts = []

    # Step 1: Index affected regions by file
    file_index: dict[str, list[tuple[str, str, ASTRegion]]] = {}
    # file_path -> [(plugin_id, rule_id, region), ...]

    for plugin_id, impact_map in impact_maps.items():
        for file_impact in impact_map.files:
            for rule_match in file_impact.matched_rules:
                for region in file_impact.affected_regions:
                    file_index.setdefault(file_impact.file_path, []).append(
                        (plugin_id, rule_match.rule_id, region)
                    )

    # Step 2: Find overlapping regions
    for file_path, entries in file_index.items():
        for i, (pid_a, rid_a, reg_a) in enumerate(entries):
            for j, (pid_b, rid_b, reg_b) in enumerate(entries):
                if j <= i or pid_a == pid_b:
                    continue  # Skip same-plugin and duplicate pairs

                if regions_overlap(reg_a, reg_b):
                    # Step 3: Check cross-reference relationship
                    relationship = get_relationship(plugins, pid_a, pid_b)

                    if relationship == "takes_precedence":
                        # Step 4: Suppress lower-priority rule
                        # (already handled by precedence filtering)
                        pass
                    elif relationship in ("does_not_override", "complementary", None):
                        # Step 5: Check if remediation strategies conflict
                        rule_a = get_rule(plugins, pid_a, rid_a)
                        rule_b = get_rule(plugins, pid_b, rid_b)

                        if strategies_conflict(rule_a.remediation, rule_b.remediation):
                            conflicts.append(ConflictRecord(
                                conflicting_rule_ids=[
                                    f"{pid_a}/{rid_a}",
                                    f"{pid_b}/{rid_b}",
                                ],
                                affected_regions=[reg_a, reg_b],
                                description=f"Rules {rid_a} and {rid_b} produce "
                                    f"conflicting changes to {file_path} "
                                    f"lines {reg_a.start_line}-{reg_a.end_line}",
                            ))

    return conflicts


def regions_overlap(a: ASTRegion, b: ASTRegion) -> bool:
    """Two AST regions overlap if their line ranges intersect."""
    return a.start_line <= b.end_line and b.start_line <= a.end_line


def strategies_conflict(a: Remediation, b: Remediation) -> bool:
    """Two remediation strategies conflict if they modify the same code region
    with different transformations. Same strategy with same template is not a conflict."""
    if a.strategy == b.strategy and a.template == b.template:
        return False  # Same fix from two regulations — deduplicate, don't conflict
    return True  # Different strategies on same region — conflict
```

### 6.3 File-Level Analysis Caching

```python
def compute_cache_key(
    file_content: bytes,
    plugin_version: str,
    agent_version: str,
) -> str:
    """
    Cache key for file-level analysis results.
    If the file content, plugin version, and agent version haven't changed,
    the analysis result is deterministic (given model version pinning).

    Returns SHA-256 hex digest (64 chars).
    """
    hasher = hashlib.sha256()
    hasher.update(file_content)
    hasher.update(plugin_version.encode())
    hasher.update(agent_version.encode())
    return hasher.hexdigest()


async def analyze_with_cache(
    file_path: Path,
    file_content: bytes,
    plugin: RegulationPlugin,
    agent_version: str,
    cache_repo: FileCacheRepository,
) -> Optional[FileImpact]:
    """
    Check cache before running analysis. Cache hit avoids LLM calls.

    Cache invalidation:
    - File content changed -> different SHA256 -> cache miss
    - Plugin version changed -> different SHA256 -> cache miss
    - Agent version changed -> different SHA256 -> cache miss
    - Model version changed -> agent_version includes model version -> cache miss
    - Cache expired (7 days TTL) -> cache miss
    """
    key = compute_cache_key(file_content, plugin.version, agent_version)

    cached = await cache_repo.get(key)
    if cached and cached.expires_at > datetime.now(UTC):
        return FileImpact.model_validate(cached.result)

    # Cache miss: run full analysis
    result = await run_analysis(file_path, file_content, plugin)

    # Store in cache
    await cache_repo.set(key, result.model_dump(), ttl_days=7)

    return result
```

### 6.4 Audit Entry Signing

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
import json
import base64


class AuditSigner:
    """
    Signs audit entry payloads with Ed25519 for tamper detection.

    The signature covers the canonicalized JSON payload.
    Canonicalization ensures deterministic byte representation
    regardless of dict key ordering or whitespace.
    """

    def __init__(self, private_key: Ed25519PrivateKey):
        self._private_key = private_key
        self._public_key = private_key.public_key()

    def sign(self, payload: dict) -> str:
        """Sign a payload dict. Returns base64-encoded signature."""
        canonical = self._canonicalize(payload)
        signature = self._private_key.sign(canonical)
        return base64.b64encode(signature).decode("ascii")

    def verify(self, payload: dict, signature: str) -> bool:
        """Verify a payload against its signature. Returns True if valid."""
        canonical = self._canonicalize(payload)
        sig_bytes = base64.b64decode(signature)
        try:
            self._public_key.verify(sig_bytes, canonical)
            return True
        except Exception:
            return False

    @staticmethod
    def _canonicalize(payload: dict) -> bytes:
        """
        Produce deterministic JSON bytes:
        - Sort keys alphabetically
        - No whitespace
        - UTF-8 encoding
        - Ensure consistent float representation
        """
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,  # Handle UUID, datetime, etc.
        ).encode("utf-8")
```

### 6.5 Cost Estimation

```python
# Model pricing (USD per 1M tokens, approximate)
MODEL_PRICING = {
    "anthropic/claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "anthropic/claude-haiku-4-5":  {"input": 0.80, "output": 4.00},
    "openai/gpt-4o":               {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini":          {"input": 0.15, "output": 0.60},
}

# Average tokens per agent phase (empirically measured)
PHASE_TOKEN_ESTIMATES = {
    "analyze": {"input": 8000, "output": 2000, "calls": 4},
    "refactor": {"input": 4000, "output": 4000, "calls": 3},
    "test_generate": {"input": 3000, "output": 3000, "calls": 2},
    "report": {"input": 2000, "output": 2000, "calls": 1},
}


def estimate_pipeline_cost(
    repo_count: int,
    model_config: dict[str, str],  # {phase: model_name}
    plugin: RegulationPlugin,
) -> CostEstimate:
    """
    Pre-run cost estimation.
    Multiplies per-repo token estimates by model pricing.
    Applies a rule-count multiplier (more rules = more LLM calls).

    Accuracy: within 2x of actual cost (empirically validated).
    Purpose: prevent accidental expensive runs, not precise billing.
    """
    rule_multiplier = max(1.0, len(plugin.rules) / 5.0)  # Baseline: 5 rules
    total_cost = 0.0
    total_tokens = 0
    per_repo = {}

    for phase, estimates in PHASE_TOKEN_ESTIMATES.items():
        model = model_config.get(phase, "anthropic/claude-sonnet-4-6")
        pricing = MODEL_PRICING[model]

        input_tokens = int(estimates["input"] * estimates["calls"] * rule_multiplier)
        output_tokens = int(estimates["output"] * estimates["calls"] * rule_multiplier)

        phase_cost = (
            (input_tokens / 1_000_000) * pricing["input"]
            + (output_tokens / 1_000_000) * pricing["output"]
        )

        total_cost += phase_cost * repo_count
        total_tokens += (input_tokens + output_tokens) * repo_count

    per_repo_cost = total_cost / repo_count if repo_count > 0 else 0

    return CostEstimate(
        estimated_total_cost=round(total_cost, 4),
        per_repo_cost={f"avg": round(per_repo_cost, 4)},
        estimated_total_tokens=total_tokens,
        model_used=model_config.get("analyze", "anthropic/claude-sonnet-4-6"),
        exceeds_threshold=total_cost > pipeline_config.cost_threshold,
    )
```

### 6.6 Deterministic Branch Naming

```python
def generate_branch_name(regulation_id: str, rule_id: str) -> str:
    """
    Deterministic branch naming for idempotent operations.

    Format: rak/{regulation_id}/{rule_id}
    Example: rak/dora-ict-risk-2025/DORA-ICT-001

    Properties:
    - Deterministic: same inputs always produce the same branch name
    - Idempotent: re-running the pipeline reuses existing branches
    - Scoped: each rule gets its own branch (reviewable independently)
    - Identifiable: the rak/ prefix identifies framework-created branches
    """
    safe_regulation = regulation_id.replace("/", "-").replace(" ", "-").lower()
    safe_rule = rule_id.replace("/", "-").replace(" ", "-")
    return f"rak/{safe_regulation}/{safe_rule}"


def generate_workflow_id(regulation_id: str, repo_url: str, phase: str) -> str:
    """
    Deterministic Temporal workflow ID for repository-level locking.

    Temporal enforces workflow ID uniqueness — starting a workflow with an
    existing ID is rejected, preventing concurrent processing of the same repo.

    Format: rak/{phase}/{regulation_id}/{repo_hash}
    """
    repo_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:12]
    return f"rak/{phase}/{regulation_id}/{repo_hash}"
```

---

## 7. Error Handling and Retry Logic

### 7.1 Error Classification

```python
class RAKError(Exception):
    """Base exception for all framework errors."""
    pass

class PluginError(RAKError):
    """Plugin loading, validation, or template errors."""
    pass

class AnalysisError(RAKError):
    """Errors during code analysis (AST parse failure, search failure)."""
    retryable: bool = True

class RefactorError(RAKError):
    """Errors during code transformation."""
    retryable: bool = True

class TestExecutionError(RAKError):
    """Errors during sandboxed test execution."""
    retryable: bool = False  # Flaky tests should not be auto-retried

class LLMError(RAKError):
    """LLM provider errors (rate limit, timeout, content filter)."""
    retryable: bool = True

class GitError(RAKError):
    """Git operations errors (clone, push, PR creation)."""
    retryable: bool = True

class AuditError(RAKError):
    """Audit trail errors. NEVER suppressed."""
    retryable: bool = True  # Audit writes are retried aggressively
```

### 7.2 Temporal Retry Policies

```python
# Activity-level retry policies

ANALYZE_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=3,
    non_retryable_error_types=["PluginError"],  # Bad plugin = don't retry
)

REFACTOR_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=10),
    maximum_attempts=3,
    non_retryable_error_types=["PluginError"],
)

TEST_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_attempts=1,  # Tests are not retried (non-deterministic)
)

REPORT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,  # Reporting is critical — retry aggressively
    non_retryable_error_types=[],
)

# Activity timeout configuration
ACTIVITY_TIMEOUTS = {
    "estimate_cost": {
        "start_to_close_timeout": timedelta(minutes=5),
        "heartbeat_timeout": timedelta(minutes=1),
    },
    "analyze_repository": {
        "start_to_close_timeout": timedelta(minutes=30),
        "heartbeat_timeout": timedelta(minutes=5),
    },
    "refactor_repository": {
        "start_to_close_timeout": timedelta(minutes=30),
        "heartbeat_timeout": timedelta(minutes=5),
    },
    "test_repository": {
        "start_to_close_timeout": timedelta(minutes=15),
        "heartbeat_timeout": timedelta(minutes=3),
    },
    "report_results": {
        "start_to_close_timeout": timedelta(minutes=30),
        "heartbeat_timeout": timedelta(minutes=5),
    },
}
```

### 7.3 Error Flow — Activity Failure and Recovery

```mermaid
sequenceDiagram
    participant WF as Workflow
    participant TS as Temporal Server
    participant W1 as Worker 1
    participant W2 as Worker 2
    participant PG as PostgreSQL
    participant AL as AuditLogger

    WF->>TS: execute_activity(analyze_repo, retry=3)
    TS->>W1: Dispatch to Worker 1

    W1->>W1: analyze_repository(repo_A)
    W1->>W1: LLM call fails (rate limit)

    W1--xTS: Activity FAILED (LLMError, retryable)

    Note over TS: Retry attempt 1/3<br/>Wait 5s (initial_interval)

    TS->>W2: Re-dispatch to Worker 2 (or same worker)
    W2->>W2: analyze_repository(repo_A)
    W2->>W2: LLM call succeeds

    W2->>PG: INSERT audit_entries (analysis result)
    W2->>PG: UPDATE repository_progress (status=completed)
    W2-->>TS: Activity COMPLETED (ImpactMap)

    TS-->>WF: Return ImpactMap

    Note over WF: If all 3 retries fail:
    Note over WF: Activity fails permanently.
    Note over WF: Child workflow fails.
    Note over WF: Repository marked as FAILED.
    Note over WF: Other repos continue (fan-out isolation).
    Note over WF: "rak retry-failures" can retry later.
```

---

## See Also

| Document | What You'll Find |
|---|---|
| [`software-architecture.md`](software-architecture.md) | C4 model, component design, code-level abstractions |
| [`system-design.md`](system-design.md) | Deployment topology, hardware sizing, network policies |
| [`framework-spec.md`](framework-spec.md) | Abstract framework specification, plugin schema, agent contracts |
| [`data-model.md`](data-model.md) | Full database schema, indexes, JSONB payload schemas, partitioning |
| [`operations/runbook.md`](operations/runbook.md) | Failure recovery procedures, maintenance, troubleshooting |

*This document describes the code-level design. For system-level architecture, see [`software-architecture.md`](software-architecture.md). For deployment and infrastructure, see [`system-design.md`](system-design.md). For the abstract framework specification, see [`framework-spec.md`](framework-spec.md).*
