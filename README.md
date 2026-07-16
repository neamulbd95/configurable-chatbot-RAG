# RAG Chatbot Service

An interactive GenAI chatbot that follows a full RAG lifecycle — extraction from a relational database, normalization, chunking, embedding, vector indexing, retrieval, and grounded response generation — built to be **RDBMS-agnostic** and **provider-agnostic** from day one, and packaged to drop into any microservice architecture with minimal integration work.

Full requirements: [PDR-chatbot-rag.md](./PDR-chatbot-rag.md). Full task-level build plan and current implementation status: [TASK-BREAKDOWN.md](./TASK-BREAKDOWN.md).

## Summary

The service ingests rows from one or more configured tables in your relational database, turns each row (optionally joined with related child rows) into normalized text, chunks and embeds that text, and stores it in a `pgvector`-backed vector store. A `/chat` endpoint then answers natural-language questions by retrieving the most relevant chunks and asking an LLM to answer **only** from that retrieved context — every grounded answer carries citations back to the source table and row.

Both the source database engine and the LLM/embedding provider are swappable via configuration alone: no code changes are needed to point the service at PostgreSQL vs. MySQL vs. SQL Server, or at a local Ollama model vs. Azure OpenAI.

## Added Features

**Phase 1 — Core RAG pipeline**
- Config-driven extraction from a source RDBMS table, with configurable column exclusion (e.g. hiding primary/foreign keys from the embedded text) and pagination/batching
- Null-safe, type-safe normalization of structured rows into canonical text, with full lineage (`source_table`, `primary_key`, `extracted_at`)
- Sentence-aware chunking with configurable size and overlap
- Pluggable embedding and chat providers — **Ollama** (local, default) and **Azure OpenAI** (cloud), selected at runtime via config/env
- Embedding dimension validation before anything reaches the vector store
- Vector similarity search with a configurable top-K and minimum-similarity threshold
- A `/chat` endpoint that always retrieves before generating — there is no code path that lets the model answer without grounded context — and returns citations alongside every grounded answer
- `/health` and `/ready` endpoints, stateless service design, Docker/`docker-compose` setup

**Phase 2 — Extensibility**
- **Multi-table & relation-aware extraction**: ingest any number of configured tables in one run, with one-to-many child-table joins folded into the parent record's text
- **Per-table normalization templates**: override the default "field: value" rendering with a custom template per table, validated at config-load time
- **Incremental ingestion with persisted watermarks**: each table resumes from its own last-seen `updated_at` value across runs, not just within one
- **Hybrid retrieval**: blend vector similarity with Postgres full-text keyword ranking via a configurable weight (defaults to pure vector search — fully backward compatible)
- **Pluggable reranking**: a `Reranker` interface with a zero-cost no-op default and an optional cross-encoder implementation (`pip install .[rerank]`)
- **Answer confidence scoring**: every response reports a confidence score derived from retrieval similarity
- **Role-based access control**: tables can be tagged with `access_tags`; chunks inherit them, and retrieval default-denies access to any tagged chunk unless the caller presents a matching role
- **Multi-turn conversational context**: chat sessions and message history are persisted, threaded back into the prompt on each turn, and truncated by a configurable message-count/character budget so long conversations can't blow out the model's context window
- **Retrieval evaluation harness** (`scripts/eval_retrieval.py`): precision@K / recall@K against a labeled query set, for measuring hybrid-search and reranking changes against a baseline
- **Operational ingestion API**: trigger ingestion (`POST /admin/ingest`) and poll its progress/result (`GET /admin/ingest/{job_id}`) over HTTP instead of shelling into the host to run the CLI; reset ingested data (`POST /admin/vector-store/reset`) with an explicit confirmation flag, which also clears the affected tables' persisted watermarks. Gated by an optional `ADMIN_API_KEY`.
- **Source DB connectivity check** (`GET /admin/source-db/status`): a real `SELECT 1` against the source RDBMS, distinct from `/health`/`/ready` which only prove the app process is up.

**Frontend**
- **Angular chat + admin UI** ([`frontend/`](./frontend)): a chat interface (grounded answers, citations, confidence, multi-turn sessions) and an admin panel (source-DB status, ingestion trigger/poll, vector-store reset) against the API above, styled with a custom design-token system approximating EY's Motif visual language.

## USP — Why This Is Different

- **RDBMS-agnostic by construction, not by promise.** Extraction runs through SQLAlchemy Core against reflected tables, so PostgreSQL, MySQL, SQL Server, and Oracle are all one-line config changes — not four separate codepaths to maintain.
- **The vector store is never assumed to live next to the source database.** Point the service at a production PostgreSQL/MySQL/whatever for source data and a completely separate, independently-owned `pgvector` instance for embeddings — the two are configured and connected independently.
- **Grounding is enforced by control flow, not convention.** The chat service has no code path that calls the LLM without first retrieving context; an ungrounded query gets a fixed "I don't have enough information" answer instead of a hallucination.
- **Provider swaps are a config change.** Ollama for local development, Azure OpenAI for production — same code, same interfaces, both for embeddings and chat generation.
- **Built to be dropped into a microservice architecture.** Stateless, containerized, config-via-env, health/readiness endpoints, and a documented OpenAPI contract as the only integration surface — no shared code, no assumed co-located infrastructure.
- **RBAC and multi-tenancy are retrieval-time concerns, not bolted-on middleware.** Access tags travel with data from source row to chunk metadata to the retrieval SQL itself.

## Installation Guide

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) (for local development) with the `qwen3:8b` and `nomic-embed-text` models pulled — or an Azure OpenAI resource for cloud deployment
- Docker Desktop (recommended, for the source DB, vector store, and Ollama containers) — or your own PostgreSQL/MySQL/etc. instances

#### Windows notes

These affect every command below that involves `curl` or a JSON body — read this once, then the rest of the guide makes sense on Windows.

- **`python` vs `python3`.** Use `python`. On a stock Windows install, `python3` (and sometimes bare `python`) can resolve to a Microsoft Store stub that does nothing but print an install prompt. If that happens, use the `py` launcher instead: `py -3.11`.
- **PowerShell's `curl` is not curl.** PowerShell ships `curl` as a built-in alias for `Invoke-WebRequest`, which does not understand `-X`, `-H`, or `-d` the way real curl does — running the plain `curl` commands below in PowerShell fails with an error like `Cannot bind parameter 'Headers'...`. Windows 10 (1803+) and Windows 11 also ship the real curl at `C:\Windows\System32\curl.exe`, so every command below that needs to work in PowerShell uses `curl.exe` explicitly to bypass the alias.
- **JSON body quoting differs by shell.** A `-d '{"key": "value"}'` body with unescaped inner double-quotes works correctly in bash/Git Bash, but gets mangled by PowerShell's argument passing to native executables (the JSON silently arrives as `{}`, no obvious error). Wherever a command sends a JSON body containing embedded quotes, a separate PowerShell-safe version (escaped as `-d '{\"key\": \"value\"}'`) is given.
- **`cp`.** Works in PowerShell (built-in alias for `Copy-Item`) but not in Command Prompt — use `copy` there, or just use PowerShell/Git Bash instead of `cmd.exe`.

### 1. Clone and set up a virtual environment

```bash
git clone <this-repo>
cd ChatBot
python -m venv .venv
```

Activate it:

| Shell | Command |
|---|---|
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Command Prompt | `.venv\Scripts\activate.bat` |
| macOS/Linux/Git Bash | `source .venv/bin/activate` |

If PowerShell refuses with `running scripts is disabled on this system`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

Then install:

```bash
pip install -e ".[dev]"
```

Optional extras:
```bash
pip install -e ".[mysql]"    # MySQL source DB driver
pip install -e ".[mssql]"    # SQL Server source DB driver — also needs the "ODBC Driver 18 for SQL Server" installed at the OS level (a separate Microsoft installer, not a pip package)
pip install -e ".[oracle]"   # Oracle source DB driver
pip install -e ".[rerank]"   # cross-encoder reranking model support
```

### 2. Configure

```bash
cp .env.example .env
cp config/tables.example.yaml config/tables.yaml
```

Edit `.env` for your source database engine/credentials, vector store credentials, and provider choice (`ollama` or `azure_openai`). Edit `config/tables.yaml` to list the table(s) you want to ingest, their primary key, any columns to exclude, and (optionally) relations, an access-tag list, or a normalization template — see the commented examples in `config/tables.example.yaml`.

If your tables live in a non-default schema (e.g. Postgres `"esg"` instead of `"public"`, SQL Server `"dbo"`), set `SOURCE_DB_SCHEMA` in `.env` rather than hardcoding it into `tables.yaml` — which schema holds your tables is a per-environment fact (it commonly differs machine to machine), not something that belongs in a config file that's typically shared/committed. Only set `schema:` on an individual table in `tables.yaml` for the exceptions (a table living in a *different* schema than the rest). Whichever way a schema applies, that table is identified everywhere as `schema.table` (e.g. `esg.asset`) — including the `/admin/ingest` and `/admin/vector-store/reset` `tables` filter — so same-named tables in different schemas never collide.

### 3. Start infrastructure

```bash
docker compose up -d postgres-source vector-store ollama
docker compose exec ollama ollama pull qwen3:8b
docker compose exec ollama ollama pull nomic-embed-text
```

(`docker compose exec` addresses the container by its service name from `docker-compose.yml`, so there's no container-name placeholder to substitute — same command on every platform.)

(Skip `postgres-source` if you're pointing `SOURCE_DB_*` at your own existing database. Add `--profile cross-engine` to also start the `mysql-source` service.)

### 4. Run the API

```bash
uvicorn ragchatbot.api.main:app --reload
```

- `GET /health`, `GET /ready` — service liveness (the process is up — not a database connectivity check)
- `POST /chat` — `{"message": "...", "session_id": "...", "roles": ["..."]}` → grounded answer with citations, confidence score, and session ID
- `GET /docs` — interactive OpenAPI documentation
- `GET /admin/source-db/status` — actual source-DB connectivity check (`SELECT 1`), not just app liveness — see below
- `POST /admin/ingest`, `GET /admin/ingest/{job_id}`, `POST /admin/vector-store/reset` — see below

Set `ADMIN_API_KEY` in `.env` before exposing this service anywhere but your own machine — without it, `/admin/*` is unauthenticated (a startup log warns you of this every time).

### 5. Run ingestion

Replace `YOUR_ADMIN_API_KEY` below with your actual key from `.env` (or drop the `-H "X-Admin-Api-Key: ..."` argument entirely if you left `ADMIN_API_KEY` unset for local dev).

**Optional but recommended first: check the source DB is actually reachable**, especially after moving the service to a new machine or changing `SOURCE_DB_*`/`SOURCE_DB_SCHEMA` — a failed ingestion job is a lot easier to read as a connectivity problem before you've also introduced a table-not-found or a schema mismatch into the mix:

```bash
curl http://localhost:8000/admin/source-db/status -H "X-Admin-Api-Key: YOUR_ADMIN_API_KEY"
# -> {"connected": true, "engine": "postgresql", "host": "...", "port": 5432, "database": "...", "source_schema": "esg", "error": null}
```

`"connected": false` comes with a populated `"error"` (the raw driver exception) instead of a stack trace — bounded by `SOURCE_DB_CONNECT_TIMEOUT_SECONDS` (default 10s) so an unreachable host fails fast rather than hanging.

**Recommended: trigger ingestion over the API**, so it's trackable and doesn't need shell access to wherever the service runs:

```bash
curl -X POST http://localhost:8000/admin/ingest -H "X-Admin-Api-Key: YOUR_ADMIN_API_KEY" -H "Content-Type: application/json" -d '{}'
# -> {"job_id": "...", "status": "pending"}

curl http://localhost:8000/admin/ingest/<job_id> -H "X-Admin-Api-Key: YOUR_ADMIN_API_KEY"
# -> {"status": "running" | "succeeded" | "failed", "stats": {...}, "error": null, ...}
```

PowerShell — same two calls (uses `curl.exe`; see Windows notes above):

```powershell
curl.exe -X POST http://localhost:8000/admin/ingest -H "X-Admin-Api-Key: YOUR_ADMIN_API_KEY" -H "Content-Type: application/json" -d '{}'
curl.exe http://localhost:8000/admin/ingest/<job_id> -H "X-Admin-Api-Key: YOUR_ADMIN_API_KEY"
```

Omit `"tables"` in the body to ingest everything in `config/tables.yaml`, or pass `{"tables": ["products"]}` to ingest a subset. The run happens in the background — the POST returns immediately with a `job_id`, and you poll the GET endpoint for progress/result. Each table resumes from its own persisted watermark on subsequent runs.

To wipe ingested data (e.g. before a clean re-ingest), reset the vector store — this is destructive and requires an explicit confirmation flag:

```bash
curl -X POST http://localhost:8000/admin/vector-store/reset -H "X-Admin-Api-Key: YOUR_ADMIN_API_KEY" -H "Content-Type: application/json" -d '{"tables": ["products"], "confirm": true}'
```

PowerShell (the embedded double-quotes need escaping differently — see Windows notes above):

```powershell
curl.exe -X POST http://localhost:8000/admin/vector-store/reset -H "X-Admin-Api-Key: YOUR_ADMIN_API_KEY" -H "Content-Type: application/json" -d '{\"tables\": [\"products\"], \"confirm\": true}'
```

Omit `"tables"` (or pass an empty list) to reset everything. Resetting a table also clears its persisted watermark, so the next ingestion run does a full re-scan instead of silently skipping rows that no longer exist in the vector store.

**Alternative: CLI**, useful for cron jobs or bootstrapping without a running API process:

```bash
python -m ragchatbot.ingestion.pipeline
```

Same underlying pipeline, run synchronously in the foreground for every table in `config/tables.yaml`.

### 6. Run tests

```bash
pytest
ruff check src tests scripts
```

### Running with Docker Compose (full stack)

```bash
docker compose up --build
```

Builds and runs the app itself alongside its infrastructure, wired together via the compose network.

### Evaluating retrieval quality

```bash
cp config/eval_set.example.yaml config/eval_set.yaml   # fill in real queries + expected record IDs
python scripts/eval_retrieval.py config/eval_set.yaml
```

### 7. Run the frontend

An Angular chat + admin UI lives in [`frontend/`](./frontend). It needs the API's CORS to allow its origin — set in `.env`:

```bash
CORS_ALLOWED_ORIGINS=http://localhost:4200   # already the default
```

```bash
cd frontend
npm install
npx ng serve
```

Open `http://localhost:4200`. See [`frontend/README.md`](./frontend/README.md) for details, including the design-system approach (no public Angular package for EY's Motif design system was found, so it's approximated with custom tokens/components — see that README for specifics) and what wasn't verified (no browser-rendering check was possible in the build environment; verified instead at the network level — see that file for exactly what was and wasn't tested).

---

**Current implementation status:** Phase 1 and Phase 2 application logic is implemented, covered by unit tests, and has been exercised end to end against live infrastructure (real PostgreSQL source + pgvector vector store + Ollama) — ingestion (including relation joins), grounded `/chat` with citations, multi-turn session persistence, and the admin ingest/reset APIs (auth, confirm-guard, actual deletion) all verified working. Not yet live-validated: the MySQL/SQL Server/Oracle source-engine paths (only PostgreSQL has been exercised live), the optional cross-encoder reranker (`pip install .[rerank]`), Azure OpenAI as a live provider, and load/latency testing against the NFR targets. See [TASK-BREAKDOWN.md](./TASK-BREAKDOWN.md) for the full status legend and per-item markers.
