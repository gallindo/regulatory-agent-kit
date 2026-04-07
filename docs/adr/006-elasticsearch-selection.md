# ADR-006: Elasticsearch as Regulatory Knowledge Base

**Status:** Accepted
**Date:** 2026-03-27
**Decision Makers:** Engineering Team
**Related:** [ADR-003](003-database-selection.md) (PostgreSQL selection), [ADR-004](004-python-stack.md) (Python stack)

---

## Context

`regulatory-agent-kit` requires a search index for the regulatory knowledge base — the corpus of regulatory documents, rule descriptions, and contextual information that the Analyzer Agent queries when evaluating code against regulations. This search capability is distinct from the primary data store (PostgreSQL, selected in [ADR-003](003-database-selection.md)).

The knowledge base must support:

| Requirement | Description |
|---|---|
| **Full-text search** | Query regulatory documents by keywords, article numbers, rule descriptions |
| **Semantic search** | Dense vector similarity search for RAG (Retrieval-Augmented Generation) |
| **Structured filtering** | Filter by regulation_id, severity, jurisdiction, effective_date |
| **Bulk indexing** | Index 100+ regulation plugins at startup |
| **Low-latency reads** | < 100ms query latency for Analyzer Agent calls |
| **Self-hosted option** | Must be deployable on-premise for air-gapped environments |

### Data Characteristics

The regulatory knowledge base has two indexes (defined in [`data-model.md`](../data-model.md)):

1. **`rak-regulations`** — Rule metadata: rule ID, description, severity, regulation_id, jurisdiction (keyword fields + text search)
2. **`rak-regulation-context`** — Chunked regulatory document text for RAG: document chunks with 1536-dimensional dense vector embeddings (cosine similarity)

The data volume is modest (thousands of rules, not millions), but query quality is critical — missed matches mean missed compliance violations.

---

## Options

### Option A: Elasticsearch 8.x

A mature, full-featured search engine with native support for both full-text and dense vector search (kNN).

**Strengths:**
- Native kNN vector search (dense_vector field type) for semantic similarity
- Mature full-text search (BM25) with analyzers, stemming, synonyms
- Structured filtering with keyword fields and range queries
- Battle-tested at scale in production environments
- Rich ecosystem: Kibana for debugging, extensive client libraries
- `elasticsearch-py` async client (`AsyncElasticsearch`) integrates well with the async Python stack

**Weaknesses:**
- Heavyweight operational dependency (JVM, 2+ GB RAM minimum per node)
- Licensing: SSPL / Elastic License 2.0 (not Apache 2.0) — impacts some enterprise adoption
- Cluster management overhead (shard allocation, replica tuning)

### Option B: OpenSearch

AWS-managed fork of Elasticsearch 7.x, now diverged with its own features.

**Strengths:**
- Apache 2.0 licensed (addresses Elasticsearch licensing concern)
- AWS-managed option (Amazon OpenSearch Service) reduces operational overhead
- kNN vector search support
- API-compatible with Elasticsearch for most operations

**Weaknesses:**
- Feature parity lags Elasticsearch 8.x (e.g., newer kNN improvements)
- Self-hosted version has less community adoption than Elasticsearch
- Two ecosystems to track (OpenSearch Dashboard vs. Kibana)

### Option C: PostgreSQL Full-Text Search + pgvector

Use the existing PostgreSQL instance with `tsvector`/`tsquery` for text search and `pgvector` extension for vector similarity.

**Strengths:**
- No additional infrastructure (reuses PostgreSQL from [ADR-003](003-database-selection.md))
- Simplifies deployment, especially Lite Mode
- `pgvector` supports cosine similarity, L2 distance, inner product
- Operational simplicity (single database to manage)

**Weaknesses:**
- PostgreSQL full-text search is less capable than Elasticsearch (no custom analyzers, limited relevance tuning)
- `pgvector` performance degrades significantly above ~1M vectors (not a concern at current scale, but limits future growth)
- No equivalent of Elasticsearch's `nested` queries for structured + text combined queries
- Mixing search workload with transactional workload on the same instance risks resource contention

### Option D: Typesense / Meilisearch

Lightweight, developer-friendly search engines.

**Strengths:**
- Simple to deploy and operate (single binary)
- Low resource footprint
- Fast indexing and search for small datasets

**Weaknesses:**
- No native dense vector search (Typesense added basic vector search recently; Meilisearch has experimental support)
- Limited structured filtering capabilities compared to Elasticsearch
- Smaller ecosystem, fewer production references in enterprise environments
- Would need a separate vector store for RAG, adding complexity

---

## Decision

**Use Elasticsearch 8.x as the regulatory knowledge base.**

### Rationale

1. **Vector search maturity:** Elasticsearch 8.x has the most mature kNN vector search implementation, critical for RAG-based context retrieval in the Analyzer Agent.
2. **Combined search:** The ability to combine full-text (BM25), vector (kNN), and structured (keyword/range) queries in a single request matches the Analyzer Agent's access pattern exactly.
3. **Production readiness:** Elasticsearch is the de facto standard for search in enterprise environments. Financial institutions (the primary target market) already operate Elasticsearch clusters.
4. **Optional dependency:** Elasticsearch is not required for Lite Mode. The Analyzer Agent degrades gracefully — it skips the `es_search` tool and relies on LLM context from plugin YAML alone.

### Licensing Mitigation

The SSPL / Elastic License 2.0 applies to the Elasticsearch server binary, not to the client library (`elasticsearch-py`, which is Apache 2.0). Since `regulatory-agent-kit` only depends on the client library, the licensing concern does not affect the framework's Apache 2.0 license. Organizations that prefer Apache 2.0 for the server can substitute OpenSearch as a drop-in replacement — the `SearchClient` abstraction in `implementation-design.md` uses only API-compatible operations.

---

## Consequences

**Positive:**
- High-quality regulatory context retrieval for the Analyzer Agent
- Familiar technology for enterprise adopters
- Clean separation of search workload from transactional workload

**Negative:**
- Additional infrastructure component to deploy and manage (JVM, 3-node cluster in production)
- Increases minimum resource requirements for full-stack Docker Compose (adds ~2 GB RAM)
- Not required for Lite Mode, but the feature gap (no semantic search) should be documented

**Neutral:**
- OpenSearch can be substituted without code changes (API-compatible)
- Future option: evaluate `pgvector` as a Lite Mode search backend if demand exists
