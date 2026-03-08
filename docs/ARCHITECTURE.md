# Architecture

## MVP Shape

The MVP is implemented as a modular monolith in one FastAPI deployment unit.

- `vision` boundary: deterministic demo detector with a stable adapter interface
- `knowledge` boundary: document ingestion, chunking, lexical retrieval
- `agent` boundary: report synthesis, guardrails, trace persistence, notifications
- `api` boundary: source, inference, event, report, QA, and metrics endpoints
- `ui` boundary: server-rendered dashboard

## Why This Shape

- The repository started from an empty workspace.
- The PRD requires end-to-end functionality sooner than service extraction.
- Docker-based verification is simpler with one deployable process.

## Planned Extraction Path

- Extract `vision` into `services/vision-service`
- Extract `agent` into `services/agent-service`
- Replace lexical retrieval with pgvector or Qdrant
- Replace deterministic generator with a real detector or VLM