# Execution Plan & Feature-Level Task Breakdown: Chatbot RAG

**Related:** [PDR-chatbot-rag.md](./PDR-chatbot-rag.md) (PDR-CHATBOT-RAG-001, v1.2)
**Status:** Phase 1 and Phase 2 implemented in code (unit-tested); live-infrastructure validation pending — pending ADR-CHATBOT-RAG-001 for formal architecture sign-off
**Owner:** Neamul Haque Khan
**Date:** 2026-07-09 (last updated)

---

## 0. Assumptions & Open Decisions

These are not fixed by the PDR. Treat as working defaults until an ADR confirms them — flagged inline where a task depends on one.

| Decision | Default assumption | Alternative if wrong |
|---|---|---|
| Language/framework | Python 3.11+, FastAPI | Node/TypeScript + Express/Fastify |
| Source DB access | RDBMS-agnostic via SQLAlchemy core engine, dialect selected by config (`postgresql+psycopg`, `mysql+pymysql`, `mssql+pyodbc`, `oracle+oracledb`, ...) | Hand-rolled per-dialect connectors |
| Vector store | `pgvector` on a **dedicated** PostgreSQL instance, configured independently of the source RDBMS — never assumed co-located | Standalone Qdrant/Chroma/Weaviate |
| Orchestration | Hand-rolled pipeline, thin provider adapters | LangChain / LlamaIndex |
| Config format | YAML + env var overrides (`pydantic-settings`) | Pure env vars / JSON config |
| Packaging | Stateless service, Docker image, 12-factor config, health/readiness endpoints — deployable standalone or as one microservice in a larger system | Library/SDK embedded directly in a host app |

> **Portability constraint (PDR v1.2):** the source RDBMS is not assumed to be PostgreSQL. Extraction must go through a dialect-agnostic data-access layer, and the vector store must be reachable via its own connection config so the service can point at any supported source engine without code changes. See [PDR §1.2, §2.1, FR-1.6–1.7, NFR-1.7–1.8](./PDR-chatbot-rag.md).

---

## 1. Architecture Overview

```
Source RDBMS (PostgreSQL | MySQL | SQL Server | Oracle | ...)
   │
   ▼
[RDBMS Adapter]  ──config: engine/dialect, table list, PK/FK exclusions, batching──▶ Source Record
   │
   ▼
[Normalization] ──config: per-table template (Phase 2)──▶ Normalized Record (+lineage)
   │
   ▼
[Chunking] ──config: strategy, size, overlap──▶ Chunk Record
   │
   ▼
[Embedding Provider Adapter] ──config: Ollama | Azure OpenAI──▶ vector
   │
   ▼
[Vector Store] (pgvector, independently configured — not assumed co-located with source RDBMS) ── chunk + embedding + metadata
   │
   ▼
[Retrieval Pipeline] ──query embed → similarity search → threshold filter──▶ Context Package
   │
   ▼
[Chat Service] ──retrieval-gated generation──▶ [LLM Provider Adapter] (Ollama | Azure OpenAI)
   │
   ▼
[Chat API] ──/chat endpoint, citations, session id──▶ Frontend / other microservices
```

Three points vary by deployment and are each hidden behind a config-selected adapter: the **source RDBMS engine**, the **embedding provider**, and the **chat provider**. Every other stage is engine/provider-agnostic. The service itself has no hard dependency on infrastructure belonging to a specific host app, so it can be deployed standalone or embedded as one microservice in a larger system.

---

## 2. Execution Phases

- **Phase 0 — Foundation:** repo scaffolding, config schema, provider adapter interfaces, DB connectivity.
- **Phase 1 — Core RAG (PDR §3.1–3.5):** single-table ingestion through grounded chat responses, both providers working, NFRs instrumented.
- **Phase 2 — Extensibility (PDR §3.6):** multi-table/relational extraction, table-specific normalization, hybrid retrieval + reranking, RBAC, conversational context.

---

## 3. Feature-Level Task Breakdown

> **Status legend:** `[x]` = implemented and unit-tested (pure logic) or verified via `TestClient`/ruff.
> `[~]` = implemented but **not yet validated against live infrastructure** (real Postgres/MySQL/Ollama/Azure) —
> no Docker Desktop / live LLM was available in the build environment. `[ ]` = not started.

### Epic 0: Project & Config Foundation
- [x] Initialize repo structure (`ingestion/`, `retrieval/`, `chat/`, `providers/`, `config/`, `tests/`)
- [x] Define config schema: source RDBMS engine/connection, table list, column include/exclude (PK/FK), chunking params, provider selection, thresholds, vector store connection (separate from source) — **backs FR-1.2, FR-1.6–1.7, FR-5.3**
- [x] `pydantic-settings` (or equivalent) config loader with env override support
- [x] Define provider adapter interfaces: `EmbeddingProvider`, `ChatProvider` (both must support Ollama + Azure OpenAI implementations) — **backs FR-5.1–5.3**
- [x] Define `SourceRDBMSAdapter` interface (engine-agnostic connection/session management via SQLAlchemy core) + secrets from env/secret store — **backs FR-1.1, FR-1.6, NFR-1.6**
- [x] Vector store connection management, wired independently of the source RDBMS adapter — **backs FR-1.7**
- [ ] CI scaffold: lint, type-check, unit test runner *(pytest/ruff run locally; no CI workflow file committed yet)*

### Epic 0b: RDBMS Portability & Microservice Packaging
- [x] Dialect abstraction layer on top of SQLAlchemy core: connection string builder per engine, pagination/quoting/type-mapping handled per dialect — **FR-1.1, FR-1.6**
- [ ] Adapter test matrix: run the extraction test suite against PostgreSQL and at least one other engine (e.g., MySQL via Docker/testcontainers) — **NFR-1.7** *(docker-compose service exists; not yet run)*
- [ ] Verify vector store and source RDBMS can point at different engines/hosts with zero code changes (config-only swap test) — **FR-1.7** *(design supports it; not live-verified)*
- [x] Containerize the service (Dockerfile, `.dockerignore`), stateless process design (no local disk state) — **NFR-1.8** *(image not yet built/run)*
- [x] Health (`/health`) and readiness (`/ready`) endpoints for orchestrator/mesh integration — **NFR-1.8**
- [x] Document the API contract (OpenAPI) as the sole integration surface — FastAPI auto-generates it at `/docs` — **NFR-1.8**

### Epic 1: Data Extraction & Normalization (FR-1.1–1.7)
- [x] Table extractor: paginated/batched row fetch from configured table via the dialect-agnostic adapter — **FR-1.1, FR-1.6**
- [x] Per-table (and per-relation) `schema` config for non-default Postgres/SQL Server/Oracle schemas; tables are identified as `schema.table` everywhere (record IDs, watermarks, admin API filters) so same-named tables in different schemas never collide — **FR-1.1**
- [x] Column exclusion logic (PK/FK excluded from normalized text but retained as metadata) — **FR-1.2**
- [x] Null-safe, type-safe normalization function → canonical text field — **FR-1.3**
- [x] Lineage stamping: `source_table`, `primary_key`, `extracted_at` — **FR-1.4**
- [x] Incremental watermark support via `updated_at` column, persisted across runs — **FR-1.5**
- [x] Unit tests: null handling, type coercion, template rendering
- [ ] Cross-engine integration tests (PostgreSQL + one other engine) proving identical extraction behavior — **FR-1.1, NFR-1.7**

### Epic 2: Chunking & Embeddings (FR-2.1–2.4)
- [x] Sentence-aware chunker with configurable size/overlap — **FR-2.1**
- [x] Embedding adapter: Ollama (`nomic-embed-text`) implementation — **FR-2.2**
- [x] Embedding adapter: Azure OpenAI implementation (same interface) — **FR-2.2, FR-5.2**
- [x] Dimension validation on embed output; reject/flag mismatches — **FR-2.3**
- [x] Persist chunk + embedding + metadata to `pgvector` with stable IDs — **FR-2.4**
- [x] Unit tests: chunk boundaries, overlap correctness

### Epic 3: Retrieval Pipeline (FR-3.1–3.4)
- [x] Query embedding using the active embedding provider — **FR-3.1**
- [x] Vector similarity search, configurable top-K — **FR-3.1**
- [x] Similarity threshold filter (configurable) — **FR-3.2**
- [x] Attach citations (source table + row key) to each result — **FR-3.3**
- [x] Assemble standardized context package schema for the chat service — **FR-3.4**
- [ ] Retrieval latency instrumentation (p95 target) — **NFR-1.1**
- [x] Live integration test: top-K correctness, threshold exclusion against a real vector store — verified 2026-07-12 against pgvector with real Ollama embeddings

### Epic 4: Chat Service & API (FR-4.1–4.4)
- [x] `/chat` endpoint: request/response contract (auto-documented via FastAPI OpenAPI) — **FR-4.1**
- [x] Orchestration: retrieval called before generation, no ungrounded fallback path — **FR-4.2**
- [x] Session ID acceptance + persistence, now also feeding multi-turn context (FR-6.11) — **FR-4.3**
- [x] Include citations in the answer payload — **FR-4.4**
- [ ] End-to-end latency instrumentation (p95 target, excluding UI render) — **NFR-1.2**
- [x] Live integration test: full ask → retrieve → generate → citation round trip — verified 2026-07-12 end-to-end (Ollama qwen3:8b), including multi-turn session persistence

### Epic 5: Provider Configurability (FR-5.1–5.3)
- [x] Ollama defaults wired (`qwen3:8b` chat, `nomic-embed-text` embed) — **FR-5.1**
- [x] Azure OpenAI deployment config (endpoint, deployment name, api version, key/managed identity) — **FR-5.2**
- [x] Runtime provider selection via config/env, unit-tested at the factory level — **FR-5.3**
- [ ] Live acceptance test: identical query run against both providers

### Epic 6: Observability & NFR Validation
- [x] Basic logging across pipeline stages (ingestion, chat)
- [ ] Metrics: retrieval latency, chat latency, ingestion throughput — **NFR-1.1–1.3**
- [x] Citation coverage: grounded answers always carry citations, ungrounded ones never do — enforced by `ChatService` control flow — **NFR-1.5**
- [x] Basic uptime/health endpoint for pilot availability tracking — **NFR-1.4**

### Epic 7: Testing & QA (Phase 1 exit criteria)
- [x] Unit test coverage for extraction, normalization, chunking, retrieval, chat service logic
- [x] Live integration test: one-table ingest → query → grounded answer with citation — verified 2026-07-12 (see Epic 4)
- [ ] Load/perf check against NFR-1.1–1.3 targets
- [ ] Live config-driven provider switch smoke test (Ollama ↔ Azure OpenAI) — Ollama side verified live; Azure OpenAI still untested live

---

## Phase 2 Epics (PDR §3.6)

> Same status legend as Phase 1 above — Phase 2 logic is implemented and unit-tested the same way, with the same live-infrastructure caveat.

### Epic 8: Multi-Table & Relation-Aware Extraction (FR-6.1–6.3)
- [x] Extend extractor to process a list of tables in one ingestion run — **FR-6.1** *(already generalized in Phase 1's pipeline loop)*
- [x] Relation/join-aware extraction merging related rows into one normalized record — **FR-6.2**
- [x] Per-table independent `updated_at` watermark tracking, persisted in `ingestion_watermarks` — **FR-6.3**

### Epic 9: Table-Specific Normalization (FR-6.4–6.5)
- [x] Per-table normalization template config (`TableConfig.normalization_template`) — **FR-6.4**
- [x] Template syntax validated at config-load time (pydantic validator); unknown-column references fail fast at first-row ingestion with `NormalizationTemplateError` — **FR-6.5**

### Epic 10: Hybrid Retrieval & Reranking (FR-6.6–6.8)
- [x] Keyword search (Postgres full-text `ts_rank_cd`) alongside vector search — **FR-6.6**
- [x] Configurable merge/weighting strategy (`retrieval_keyword_weight`, 0 = pure vector, backward compatible) — **FR-6.6**
- [~] Cross-encoder reranking of top-N candidates — **FR-6.7** *(pluggable `Reranker` interface + `CrossEncoderReranker` implemented; requires the optional `pip install .[rerank]` extra — not installed/exercised with a real model in this pass)*
- [x] Answer confidence score in response payload (`ChatResponse.confidence`) — **FR-6.8**
- [ ] Latency budget check against reranking overhead — **NFR-2.1**

### Epic 11: Access Control (FR-6.9–6.10)
- [x] Role/permission model for retrieval-time filtering (`passes_access_filter`, default-deny for tagged chunks) — **FR-6.9**
- [x] Propagate `access_tags` from table config → chunk metadata — **FR-6.10**
- [ ] Default-deny enforcement test against a live vector store: 100% of results respect caller scope — **NFR-2.2** *(filter logic itself is unit-tested; SQL-level integration not yet run)*

### Epic 12: Conversational Context (FR-6.11–6.13)
- [x] Chat session record persistence (`chat_sessions`: `session_id`, `user_id`, timestamps) — backs FR-4.3/FR-6.12
- [x] Chat message record persistence (`chat_messages`: `message_id`, `role`, `content`, `citations`) — **FR-6.12**
- [x] Multi-turn context assembly into the message list within a configurable window — **FR-6.11**
- [x] Truncation strategy for long sessions (`apply_history_budget`, message-count + char-budget sliding window) — **FR-6.13** *(summarization not implemented — truncation satisfies the requirement's "truncated/summarized" wording; documented as a future extension point)*
- [ ] Latency check for history retrieval + prompt assembly — **NFR-2.4**

### Epic 13: Benchmarking & Quality Dashboards
- [x] Retrieval quality eval script (`scripts/eval_retrieval.py`): precision@K/recall@K against a labeled eval set — usable for a before/after reranking baseline
- [ ] Dashboard for ingestion throughput, latency, citation coverage over time *(out of scope for this pass — no metrics backend chosen yet; the eval script and logging are the current foundation for one)*

### Epic 14: Operational Ingestion API (beyond original scope)
- [x] `POST /admin/ingest` — trigger an ingestion run (optionally scoped to a subset of tables) as a trackable background job instead of requiring shell access to run the CLI
- [x] `GET /admin/ingest/{job_id}` — poll job status/stats/error, persisted in the vector-store DB (`ingestion_jobs` table) so any worker can serve the read
- [x] `POST /admin/vector-store/reset` — delete ingested chunks (optionally scoped to tables) and their persisted watermarks together, so a reset can't leave a stale watermark that skips rows on the next run; requires an explicit `confirm: true` to guard against accidental full wipes
- [x] `ADMIN_API_KEY`-gated (`X-Admin-Api-Key` header) — unauthenticated only when the key is left unset, with a startup warning log in that case
- [x] Live validation of all three endpoints against a running Postgres + Ollama stack — verified 2026-07-12: ingest (with relation join), job status polling, and reset (auth rejection, confirm-guard, actual deletion) all confirmed against real containers

---

## 4. Suggested Build Order

1. Epic 0 (foundation) → unblocks everything
2. Epic 0b (RDBMS portability + packaging) started alongside Epic 0 — the dialect abstraction must exist *before* Epic 1 is built on top of it, not retrofitted after
3. Epic 1 → Epic 2 → Epic 3 (ingestion-to-retrieval pipeline, one table)
4. Epic 4 + Epic 5 in parallel (chat API and provider adapters both depend on Epic 3 output shape, not on each other)
5. Epic 6 (observability) threaded in alongside 1–5, not deferred to the end
6. Epic 7 as Phase 1 exit gate — must include the Epic 0b cross-engine and containerized-deploy checks
7. Phase 2 epics (8–13) — Epic 8/9 (multi-table + normalization) before Epic 10 (hybrid retrieval needs multi-table data to be meaningful); Epic 11 (RBAC) can run in parallel; Epic 12 (conversational context) is independent and can start anytime after Epic 4

## 5. Definition of Done (per phase)

- **Phase 1:** All Epic 0, 0b, 1–7 tasks checked, PDR §1.3 Success Criteria met, NFR-1.1–1.8 targets validated in a load test (including cross-engine extraction and containerized deployment), provider swap smoke test passing.
- **Phase 2:** All Epic 8–13 tasks checked, NFR-2.1–2.4 targets validated, RBAC default-deny test passing, eval set shows reranking improves precision@K over baseline.

**Current state (2026-07-12):** all Phase 1 and Phase 2 application logic is implemented, covered by 49 unit tests, and has been exercised live end-to-end against real PostgreSQL + pgvector + Ollama (ingestion including relation joins, grounded `/chat` with citations, multi-turn session persistence, and all three admin API endpoints — see Epics 4, 7, 14 above). Still needing live validation, per the remaining `[~]`/`[ ]` markers above: MySQL/SQL Server/Oracle as a source engine (only PostgreSQL tested live), RBAC enforcement against a live vector store (no `access_tags` configured in the tested run), hybrid-search SQL execution, the optional cross-encoder reranker (`pip install .[rerank]`), Azure OpenAI as a live provider, and load/latency numbers against the NFR targets. Neither phase is "done" by this document's own Definition of Done until that remaining validation happens.
