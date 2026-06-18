# RAG Portfolio — Backend

Python backend for Nic's RAG "ask me anything" portfolio widget. Visitors ask natural-language
questions about Nic's background and get grounded, conversational answers (the model answers
*about* Nic, in the third person).

The design is settled and documented — this repo is **execution**. See `CLAUDE.md` for the project
constitution and `docs/` for the authoritative design + decision logs.

## What's here

- **Layer 1 — Ingestion** (`ingest/`): Notion → chunk → hosted Pinecone Inference embedding →
  vector store (Chroma local / Pinecone prod).
- **Layer 2 — Query Pipeline & Serving** (`query/`): retrieve → relevance gate → grounded prompt →
  Claude Haiku 4.5 (streamed) → FastAPI `POST /v1/ask` (SSE).
- **Layer 4 cloud rollout** of the above (Lightsail + Cloudflare; Lambda + EventBridge).

> The **Layer 3 frontend widget is NOT in this repo** — it's a first-party `'use client'`
> component in Nic's existing Next.js site repo.

Embedding is a **hosted API call** — there is deliberately no `sentence-transformers` / `torch`.

**Locked decisions** (see `config.py`):

- Embedding model: **`llama-text-embed-v2` @ 384-dim**, metric **cosine**, on Pinecone Inference
  (`input_type=passage` for chunks, `query` for queries). Locked in `M0.5-01`, verified against the
  live API.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # both layers + ruff/mypy/pytest

cp .env.example .env             # then fill in the keys
```

Dependencies are split by layer as optional groups: `.[ingest]`, `.[query]`, `.[dev]` (= all).

## Checks (run before marking any ticket done)

```bash
ruff check . --fix && ruff format .
mypy .
pytest -q
```

## Backlog

Work is tracked as 43 tickets in the Notion `DB Action Items` database, linked to the RAG project
page (M1.1 split into a synthetic seed + real authoring, plus the `M4.2-03` content-swap gate). Notion is the live source of truth for status. Commit per ticket with the Req-ID in the
message, e.g. `feat(ingestion): chunker [M1.4-01 · L1 chunking]`. See `docs/Action_Items.md`.
