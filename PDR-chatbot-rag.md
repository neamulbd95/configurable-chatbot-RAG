# Product Definition & Requirements: Interactive GenAI Chatbot with RAG

**Document ID:** PDR-CHATBOT-RAG-001  
**Version:** 1.2  
**Date:** July 8, 2026  
**Owner:** Neamul Haque Khan  
**Status:** Draft  
**Related:** ADR-CHATBOT-RAG-001, IDR-CHATBOT-RAG-001

---

## 1. Executive Summary

### 1.1 Purpose
Build an interactive GenAI chatbot that follows a full RAG lifecycle, starting with structured data extraction from a configurable relational database (PostgreSQL as the default/reference implementation, with other RDBMS engines supported via config), normalization, chunking, embedding generation, vector indexing, retrieval, and grounded response generation based on the context and chat session.

### 1.2 Business Objectives
- Enable users to ask natural language questions over enterprise data.
- Provide grounded answers with source traceability and business safe wording .
- Support local development with Ollama and deployment with Azure OpenAI.
- Keep ingestion and retrieval configurable for scale from one table to many tables.
- Natural alias mapping- Users can query without schema knowledge.
- RDBMS-agnostic source connectivity — the same service works against PostgreSQL, MySQL, SQL Server, Oracle, etc. by config change only.
- Minimal-coupling design — the whole service is deployable as a standalone microservice and pluggable into other systems with minimal integration changes.

### 1.3 Success Criteria
- ✅ Chatbot answers are grounded in retrieved data.
- ✅ Structured table data is normalized before chunking.
- ✅ One-table ingestion is production-ready with multi-table extensibility.
- ✅ Config-driven model/provider switch (Ollama ↔ Azure OpenAI).
- ✅ End-to-end latency and retrieval metrics are captured.

### 1.4 Non-Goals (Phase 1)
- ❌ Multi-modal inputs (images, audio, video)
- ❌ Real-time CDC streaming ingestion
- ❌ Fine-tuning custom foundation models
- ❌ Advanced reranking pipelines (cross-encoder)
- ❌ Non-relational/NoSQL source connectors (Phase 1 is RDBMS-only; any SQL-speaking relational engine, not document/key-value/graph stores)

---

## 2. Scope

### 2.1 In Scope (Phase 1)
- RDBMS-agnostic extraction from a single configured source table (PostgreSQL as default/reference; MySQL, SQL Server, Oracle, etc. supported via config-selected driver, no code change).
- Config model supporting future multiple source tables as well configurable excluding source table column including primary key, foreign keys.
- Data normalization rules for structured rows for relational tables.
- Text chunking and embedding generation.
- Vector storage and similarity retrieval, configured and deployed independently of the source RDBMS engine.
- Chat service that orchestrates retrieval + LLM response.
- Basic frontend integration contract (API-based).
- Microservice-ready packaging: stateless service, config via env/secret store, containerizable, no dependency on infrastructure co-located with a specific consuming application.

### 2.2 Future Scope (Phase 2)
- Multiple table joins and relation-aware extraction.
- Table-specific normalization templates.
- Hybrid retrieval (vector + keyword).
- Reranking and answer confidence scoring.
- Role-based access filters in retrieval.
- Answering answers with maintaining chat session and previous message context.

> Detailed functional requirements for the above are specified in [3.6 Phase 2 Functional Requirements](#36-phase-2-functional-requirements).

---

## 3. Functional Requirements

### 3.1 Data Extraction & Normalization

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-1.1 | Extract rows from a configured RDBMS source table via a dialect-agnostic data-access layer | MUST | Data fetched with pagination/batching; works unmodified against PostgreSQL and at least one other RDBMS engine (e.g., MySQL) in test |
| FR-1.2 | Support configurable source table list | MUST | One table default, list supports future many |
| FR-1.3 | Normalize structured data into canonical text fields | MUST | Null-safe, type-safe normalization rules applied |
| FR-1.4 | Preserve lineage metadata | MUST | source_table, primary_key, extracted_at stored |
| FR-1.5 | Incremental ingestion option | SHOULD | Supports `updated_at` watermark if available |
| FR-1.6 | Runtime RDBMS engine/dialect selection via config | MUST | Switching source DB engine (e.g., PostgreSQL → MySQL) requires a config/connection-string change only, no code change |
| FR-1.7 | Isolate vector store configuration from source RDBMS configuration | MUST | Vector store connection is independently configurable and not assumed co-located with the source database |

### 3.2 Chunking & Embeddings

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-2.1 | Chunk normalized text using configurable strategy | MUST | Sentence-aware default with overlap |
| FR-2.2 | Generate embeddings from configured provider/model | MUST | Default `nomic-embed-text` via Ollama |
| FR-2.3 | Validate embedding dimension consistency | MUST | Reject/flag vectors with wrong shape |
| FR-2.4 | Store chunk + embedding + metadata | MUST | Persisted in vector store with IDs |

### 3.3 Retrieval Pipeline

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-3.1 | Embed user query and run vector similarity search | MUST | Top-K configurable |
| FR-3.2 | Filter by minimum similarity threshold | MUST | Configurable threshold enforced |
| FR-3.3 | Return citations and metadata with results | MUST | Includes source table + row key |
| FR-3.4 | Build context package for chat generation | MUST | Standard schema returned to chat service |

### 3.4 Chat Service & Frontend Integration

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-4.1 | Expose chat endpoint for UI integration | MUST | Request/response contract documented |
| FR-4.2 | Chat service invokes retrieval before generation | MUST | No ungrounded response path by default |
| FR-4.3 | Accept and persist a session ID with each request (no context-aware generation) | SHOULD | Session ID stored with message log; not yet used in prompt construction — see FR-6.11 for context-aware generation |
| FR-4.4 | Include citation references in answer payload | MUST | UI can display references |

### 3.5 Provider Configurability

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-5.1 | Local provider support (Ollama) | MUST | `qwen3:8b` + `nomic-embed-text` defaults |
| FR-5.2 | Cloud provider support (Azure OpenAI) | MUST | Model/deployment configuration supported |
| FR-5.3 | Runtime provider selection via config/env | MUST | No code changes required to switch |

### 3.6 Phase 2 Functional Requirements

#### 3.6.1 Multi-Table & Relation-Aware Extraction

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-6.1 | Support multiple source tables in a single ingestion run | MUST | Config-driven table list processed in one pipeline execution |
| FR-6.2 | Relation-aware extraction across foreign keys/joins | SHOULD | Related rows merged into one normalized record where a relation is configured |
| FR-6.3 | Per-table incremental watermark tracking | SHOULD | Each table advances its own `updated_at` cursor independently |

#### 3.6.2 Table-Specific Normalization

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-6.4 | Table-specific normalization templates | MUST | Each configured table maps to its own text-rendering template |
| FR-6.5 | Template validation at config load time | SHOULD | Missing/invalid template fields fail ingestion startup with a clear error |

#### 3.6.3 Hybrid Retrieval & Reranking

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-6.6 | Hybrid retrieval combining vector + keyword (BM25) search | MUST | Merge/weighting strategy is configurable |
| FR-6.7 | Cross-encoder reranking of top-N candidates | SHOULD | Reranked top-K precision improves over vector-only baseline on eval set |
| FR-6.8 | Answer confidence scoring | SHOULD | Confidence score returned alongside the answer payload |

#### 3.6.4 Access Control

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-6.9 | Role-based access filters applied at retrieval time | MUST | Chunks outside the caller's role/permission scope are excluded from results |
| FR-6.10 | Access metadata propagated through lineage | MUST | `access_tags`/role attributes flow from source row → normalized record → chunk metadata |

#### 3.6.5 Conversational Context

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-6.11 | Multi-turn, context-aware answer generation | MUST | Prior turns from the session are included in prompt construction within a configurable window |
| FR-6.12 | Session and message history storage | MUST | Messages persisted per FR-4.3 session ID and retrievable by session |
| FR-6.13 | Context window truncation/summarization strategy | SHOULD | Long sessions are truncated or summarized to fit the target model's context limit |

---

## 4. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1.1 | Retrieval latency | < 700ms p95 |
| NFR-1.2 | Chat response latency (end-to-end) | < 6s p95 (excluding UI render) |
| NFR-1.3 | Ingestion throughput | > 10k rows/hour (phase 1 baseline) |
| NFR-1.4 | Availability | 99% for internal pilot |
| NFR-1.5 | Traceability | 100% answer citations from retrieved chunks |
| NFR-1.6 | Security | Secrets from env/secret store, not hardcoded |
| NFR-1.7 | RDBMS portability | Data-access layer validated against ≥2 RDBMS engines (PostgreSQL + one other) via an adapter/dialect test matrix |
| NFR-1.8 | Microservice deployability | Service is stateless, container-buildable, config-driven via env/secret store, and exposes a documented API contract with no dependency on a specific consumer's infrastructure |

### 4.1 Phase 2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-2.1 | Reranking latency overhead | < 300ms p95 added to retrieval latency |
| NFR-2.2 | RBAC filter enforcement | 100% of retrieval results respect the caller's access scope |
| NFR-2.3 | Multi-table ingestion throughput | > 10k rows/hour per table, parallelizable across tables |
| NFR-2.4 | Conversational context latency overhead | < 1s p95 added for history retrieval + prompt assembly |

---

## 5. Data Contracts (Phase 1)

### 5.1 Source Record (Structured)
- `source_table`
- `primary_key`
- business columns (table-specific)
- optional `updated_at`

### 5.2 Normalized Record
- `record_id` (source_table + primary_key)
- `normalized_text`
- `attributes` (JSON)
- `lineage` (table/key/timestamp)

### 5.3 Chunk Record
- `chunk_id`
- `record_id`
- `chunk_text`
- `chunk_index`
- `embedding`
- `metadata` (lineage + attributes subset)

### 5.4 Chat Session Record (Phase 2)
- `session_id`
- `user_id` (optional)
- `created_at`
- `last_active_at`

### 5.5 Chat Message Record (Phase 2)
- `message_id`
- `session_id`
- `role` (user/assistant)
- `content`
- `citations` (optional)
- `created_at`

---

## 6. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Poor normalization reduces retrieval quality | High | Medium | Define table-specific normalization templates |
| Schema drift in source table | Medium | Medium | Column mapping config + validation checks |
| Provider switching causes output variability | Medium | Medium | Standardized prompts + acceptance tests |
| Scale issues with larger datasets | Medium | Medium | Batch ingestion + indexing strategy + partitioning |
| RBAC misconfiguration exposes restricted data | High | Low | Default-deny access filter; access tag required at ingestion (FR-6.9–6.10) |
| Reranking adds latency beyond NFR budget | Medium | Medium | Cap candidate set size before reranking; batch/async scoring |
| Long session context exceeds model context window | Medium | Medium | Sliding window + summarization strategy (FR-6.13) |
| RDBMS dialect differences (pagination, type mapping, quoting) cause extraction bugs on non-PostgreSQL engines | Medium | Medium | Dialect-abstraction layer (e.g., SQLAlchemy) + adapter test matrix across supported engines (FR-1.1, FR-1.6) |
| Coupling vector store to source RDBMS blocks portability or microservice reuse | Medium | Medium | Vector store connection configured and deployed independently of source DB (FR-1.7) |

---

## 7. Milestones

### Phase 1: Core RAG Foundation
- Source extraction from one PostgreSQL table
- Normalization and chunking pipeline
- Embedding and vector indexing
- Retrieval pipeline and citation payload
- Chat service endpoint + basic UI contract

### Phase 2: Extensibility
- Multi-table ingestion configuration with relation-aware extraction (FR-6.1–6.3)
- Table-specific normalization templates (FR-6.4–6.5)
- Incremental ingestion support
- Hybrid retrieval (vector + keyword) and cross-encoder reranking (FR-6.6–6.8)
- Role-based access filters in retrieval (FR-6.9–6.10)
- Multi-turn conversational context with persisted session history (FR-6.11–6.13)
- Benchmarking and quality dashboards

---

## 8. Approval & Sign-Off

**Product Owner:** Neamul H Khan 
**Tech Lead:** Neamul H Khan 
**Date:** July 8, 2026

---

## 9. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-05 | Engineering Team | Initial draft |
| 1.1 | 2026-07-08 | Neamul Haque Khan | Added detailed Phase 2 functional requirements (§3.6), Phase 2 NFRs (§4.1), chat session/message data contracts (§5.4–5.5), Phase 2 risks (§6), and expanded Phase 2 milestones (§7); clarified FR-4.3 scope vs. FR-6.11 |
| 1.2 | 2026-07-08 | Neamul Haque Khan | Reframed source extraction as RDBMS-agnostic (not PostgreSQL-only): updated §1.1/§1.2/§2.1, added FR-1.6–1.7, NFR-1.7–1.8, and two new risks; added non-goal excluding NoSQL sources; established microservice-pluggability as a Phase 1 requirement |

