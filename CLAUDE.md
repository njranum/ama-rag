# RAG Portfolio — Project Constitution (CLAUDE.md)

> You are working on Nic's **RAG "ask me anything" portfolio widget**. The full design is
> **already settled across all three layers.** Your job here is **execution**, not redesign.
> The portfolio value of this project is the *traceable reasoning* — design → ticket → commit —
> so keep that lineage intact at every step. Do not silently diverge from the docs; see
> **Ripple-back** below.

---

## What this repo is

This repo is the **Python backend** of the system:

- **Layer 1 — Ingestion:** Notion → chunk → embed (hosted Pinecone Inference) → vector store.
- **Layer 2 — Query Pipeline & Serving:** retrieve → relevance gate → grounded prompt →
  Claude Haiku 4.5 (streamed) → FastAPI `POST /v1/ask` (SSE).
- **Layer 4 cloud rollout** of the above (Lightsail + Cloudflare; Lambda + EventBridge).

**The frontend widget (Layer 3) lives in this repo under `web/` (monorepo).** It is a first-party
`'use client'` Next.js component, shipped via a GitHub Action → Azure pipeline (M4.3). *(Decided at
M3.1 — superseding the original plan that put Layer 3 in Nic's separate Next.js site repo, and the
M0.4 note that "no `web/` dir" applies. The `web/` Next.js app is the home for all M3 tickets.)*

---

## Authoritative documents (read before acting)

These are the source of truth. Read the relevant one(s) for whatever slice you're working,
**before** writing code. Do not reconstruct decisions from memory — they're all recorded here.

| File | What it holds |
|------|---------------|
| `docs/Project_Working_Charter.md` | The working method, conventions, and the settled-decision snapshot. Read this first. |
| `docs/RAG_System_Architecture.md` | The zoom-out: layers, data flow, cross-cutting concerns. |
| `docs/L1_Ingestion.md` | Layer 1 design + decision log (fetch, chunk, embed, store, sync/reconcile). |
| `docs/L2_Query_Pipeline.md` | Layer 2 design + decision log (retrieval, gate, prompt, generation, API contract, hosting). |
| `docs/L3_Presentation.md` | Layer 3 design + decision log (the widget — built in the *other* repo). |
| `docs/Action_Items.md` | The 41-ticket backlog: how it was generated, the milestone map, the dependency graph. |

> Adjust `docs/` to wherever you actually place these files.

---

## The backlog (the live cursor)

Implementation work is tracked as **41 tickets in the Notion `DB Action Items` database**,
linked to the RAG project page. **Notion — via MCP — is the live source of truth for what is
done.** Do not navigate the backlog by guessing the next code; query the database.

- **Data source (hardcoded — do not search for it):**
  `collection://367da49e-e112-8026-b990-000bd7b40b4e`
- **Status** is a Notion *status*-type property. Exact, case-sensitive labels:
  `Not started`, `In progress`, `Done`.
- **Ticket code shape:** `M{X}.{Y}-{NN}` (e.g. `M1.2-01`), the leading token before ` — ` in
  the title. `M{X}.{Y}` is a **slice**; `-{NN}` is a ticket within it.
- **Req IDs** on each ticket trace back to the design decision it implements (e.g. `L2: API
  contract`). Keep that thread unbroken — see Conventions.

**Work by slice, not by ticket.** The natural unit of execution is a whole `M{X}.{Y}` slice,
built in one context. Select the next slice as: *the lowest-ordered slice that still has
`Not started` tickets and whose dependency tickets are already `Done`* — never purely the next
code by arithmetic.

**Status semantics:** set a slice's tickets to `In progress` when you start; set them to `Done`
**only when their Verify criteria are met and hooks/tests pass** — never merely because you moved
on to the next thing.

### Dependency graph (sequencing is NOT linear — honour these)

- `M0.5-01` (model lock) **gates** `M1.2-01` (create the Pinecone index at the locked dimension).
- `M1.1-01a` (synthetic seed corpus) **gates the rest of M1** (ingestion needs content); `M1.1-01b` (real authoring + audit) **gates `M4.2-03`** (the content swap), **not** `M1.2`+.
- `M4.2-03` (content swap: synthetic → real + re-ingest + re-calibrate) **depends on** `M1.1-01b` + `M2.2` (calibration tooling) + `M4.2-01` (prod Pinecone), and **gates `M4.4-01`** (final verification must run against real content). If the swap changes the chips, **re-run `M4.3-01`** (re-ship widget).
- `M3.4-01` (suggested-question chips) **depends on** `M2.2-01` (the Phase-1 should-answer eval set).
- `M4.4-01` (end-to-end prod verification, incl. CORS) **depends on** `M2.4-01` (FastAPI/CORS).
- `M2.4-03` (wire widget to local API) **sequences after** the `M3.1` widget scaffold.
- Front-load the **manual** tickets — `M0.1-01`, `M0.2-01`, `M0.3-01`, `M1.1-01b`, `M3.6-02` —
  so unattended runs aren't blocked waiting on accounts, content, or a live screen-reader test.
  (`M1.1-01a`, the synthetic seed, is now **Claude**-executable — it's the part that isn't the heavy manual lift.)

---

## Conventions (these are the portfolio value — hold them)

- **Trace every commit to a decision.** Commit per ticket (or per coherent slice) with the Req-ID
  in the message, e.g. `feat(ingestion): mark-and-sweep reconcile [M1.6-02 · L1 sync strategy]`.
  The git history should read as a disciplined design→ticket→code lineage.
- **Ripple-back is mandatory.** When implementation contradicts or extends a design doc — a
  calibrated threshold value, a verified API quirk, a changed assumption — **update the doc**,
  with an *annotated* note (preserve the superseded reasoning, do not delete it) and the Req-ID.
  A rotted reasoning-log kills the portfolio piece. Flag these even when unprompted.
- **Defer, don't drop.** If something is real but unnecessary at portfolio scale, record it as a
  deliberate deferral with the reason — don't build it, don't pretend it doesn't exist.
- **Working choice vs locked decision.** Some items are labelled "working choice" (e.g. the
  embedding model). Don't treat a working choice as locked; don't reopen a locked decision.
- **Verify current facts, don't rely on memory** for anything that changes (pricing, free tiers,
  product availability, model capabilities). Several past decisions turned on exactly this.

---

## Phasing rule (do not skip ahead)

Every layer follows **local → automated → cloud**, and the backlog mirrors it
(M1–M3 are locally buildable/testable; **all Phase-3 cloud work is parked in M4**).
**Do not start M4 cloud work early.** Prove each layer locally first. Phase 1 of the query
pipeline is a plain CLI — no web server, no cloud — and exists to calibrate retrieval cheaply.

---

## Commands

> Confirm/adjust these to the actual repo setup on first run (ticket `M0.4-01` establishes the
> dependency baseline). 2026 sensible defaults shown.

```bash
# Environment (Python)
uv venv && source .venv/bin/activate     # or python -m venv .venv
uv pip install -e ".[dev]"               # core deps below

# Core runtime deps:  notion-client  pinecone  chromadb  fastapi  uvicorn  anthropic
# NOTE: package is `pinecone` (the legacy `pinecone-client` is superseded).
# NOTE: there is NO `sentence-transformers` / `torch` anywhere — embedding is a hosted API call.

# Lint + format + types  (run before considering any ticket done)
ruff check . --fix
ruff format .
mypy .                                   # or pyright

# Tests
pytest -q

# Run the query pipeline locally
python -m query.cli "What is Nic's experience with AWS?"   # Phase 1 CLI (retrieve→gate→answer)
uvicorn query.api:app --reload --port 8000                 # Phase 2 local API (M2.4, SSE)

# Run ingestion locally
python -m ingest.sync        # incremental sync (use ingest.embed_store for a full re-stamp)

# Layer 3 widget (web/ — monorepo Next.js app). Its OWN toolchain — run these for any M3+ slice
# (the Python ruff/mypy/pytest do NOT cover web/):
cd web && npm install
npm run test        # vitest (SSE parser, reducer, source grouping)
npm run typecheck   # tsc --noEmit
npm run build       # next build
npm run dev         # local widget at http://localhost:3000  (NEXT_PUBLIC_API_BASE_URL in .env.local)
```

Hooks (recommended, wire in early): a **PostToolUse** hook on `Edit|Write` running
`ruff format` + `mypy` (+ `pytest` on the touched module) so errors are caught before review;
a **PreToolUse** hook on `Bash` blocking destructive commands (`rm -rf`, force-push).

---

## Load-bearing traps (carried from the design docs — check these every time they're relevant)

- **The 384-dim default trap.** `llama-text-embed-v2` returns **1024 dims unless you explicitly
  pass `dimension=384`** *and* create the Pinecone index at 384. A mismatch is silent or a dim
  error. **Check the returned vector length is 384 once at setup.**
- **`input_type` asymmetry.** Ingestion embeds chunks as `passage`; the query pipeline embeds the
  question as `query`. Embed both the same way and retrieval quality drops. Set it on both sides.
- **Same model both sides.** Query and chunk embeddings MUST use the identical model, or cosine
  similarity is meaningless. The embedding model is the seam joining Layers 1 and 2.
- **Score normalisation.** Pinecone returns cosine *similarity* (higher = closer); Chroma defaults
  to a *distance* (lower = closer). Normalise everything to **cosine similarity, higher-is-better**
  so one threshold value travels unchanged from local Chroma to prod Pinecone.
- **Threshold is empirical, not theoretical.** The retrieval-gate threshold is *measured* in
  Phase-1 calibration (`M2.2-02`) against real content and stored as config — never hardcoded from
  a guess. Set it at the *bottom* of the should-answer/should-refuse gap.
- **Decline wording consistency.** The retrieval-gate decline and the prompt-side decline use the
  **same** bare-but-polite wording (`"Sorry, I don't have information about that."`).
- **Mark-and-sweep reconcile.** Sync is not edit-only: each run enumerates the Portfolio subtree,
  **deletes chunks of pages moved out / deleted**, and does **delete-before-upsert** per changed
  page. The vector store is its own sync state (no separate timestamp file — matters for the
  stateless Lambda). This is the safety boundary holding on *removal*, not just addition.
- **SSE contract is fixed.** `POST /v1/ask`; events `sources` → `delta`s → `done`; `error` event
  for graceful failures; **`429` *before* the stream opens** (plain JSON), never as an SSE event.
  **Both** declines are sourceless: the gate decline sends **no `sources` event**, and a
  prompt-side decline (gate passed, model still declined) has its sources dropped by
  `pipeline.resolve_sources`, which peeks the stream and withholds `sources` when the answer is
  exactly the canned decline (no latency cost on a real answer). *(Supersedes the earlier
  "prompt-side decline arrives with sources already streamed" — the server now decides before
  emitting `sources`, matching its own `DECLINE_MESSAGE`; see L2 API-contract update, 2026-07-01.)*
  `sources` carries `title`, `text`, nullable `url`, reserved nullable `anchor`.
- **CORS = dev AND prod origins.** The allowlist must contain **both** dev-loopback spellings
  `http://localhost:3000` *and* `http://127.0.0.1:3000` (Phase-2 widget testing — a browser on the
  `127.0.0.1` URL sends it as a distinct Origin) **and** the production site origin (Phase 3).
  Missing the dev origin blocks local testing on a silent CORS wall.
- **Cloudflare buffering check.** In Phase-3 verification, confirm Cloudflare passes
  `text/event-stream` through **without buffering** — a known proxy gotcha that breaks streaming.
- **Lightsail billing reality.** Stopping a Lightsail instance does **not** pause billing; $3.50/mo
  requires an IPv6-only origin (viable because Cloudflare terminates IPv4 at the edge), $5/mo with
  a public IPv4 is the no-surprises default.
- **Synthetic content during the build; the real-content swap is a launch gate.** The system is
  built and calibrated on a clearly-fictional, shape-matched persona (`M1.1-01a`). The gate
  **threshold is provisional** until re-calibrated on real content (`M4.2-03`), and the
  suggested-question **chips are synthetic** until regenerated there. A fictional persona must
  **never** reach production — `M4.2-03` must complete **before** `M4.4-01` (go-public verification)
  and before the widget ships real answers to visitors. Real authoring is `M1.1-01b` (Manual).

---

## The one genuinely open decision

**Embedding model lock** (`M0.5-01`): working choice `llama-text-embed-v2` @ 384-dim
(input length confirmed: 2048-token limit ≫ ~500-token chunks). Alternative on the same endpoint:
`multilingual-e5-large` @ 1024-dim (re-confirm input length and note it *is* an e5 model — strict
`query:`/`passage:` markers — if the lock lands there). The **strategy** (hosted, not local) is
settled; only the exact model/dimension is open. This lock gates the Pinecone index dimension.

> **RESOLVED — LOCKED (M0.5-01, 2026-06-18).** Lock = **`llama-text-embed-v2` @ 384-dim, cosine**
> (`input_type=passage` for chunks, `query` for queries). Verified against the live Pinecone
> catalogue with a 384-length test embed (1024 default avoided); recorded in `config.py`
> (`EMBED_MODEL`/`EMBED_DIM`/`EMBED_METRIC`). This decision is now closed — `M1.2-01` creates the
> index at 384/cosine.

---

## Out of scope here (don't pull these into backend work)

- **Layer 3 widget** — separate Next.js repo (see top).
- **C2: public portfolio content pages** — a content/site task that later populates each chunk's
  `url` at ingestion and activates the widget's "read more →" links. Parked as `M4.5-01 [Future]`.
- **Layer 4: operational concerns** (observability, cost monitoring, answer-quality eval) — parked
  as `M4.5-02 [Future]`. The reducer dispatch point in the widget is pre-positioned as its hook.