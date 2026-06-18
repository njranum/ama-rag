# RAG System Architecture

## Purpose

This document describes the end-to-end architecture of the personal portfolio RAG system as a stack of **discrete layers**. The system lets visitors to Nic's personal website ask natural-language questions about Nic's professional background and receive grounded, conversational answers — with the LLM answering *about* Nic in the third person, never impersonating Nic.

This is the zoom-out view. The detailed per-layer design and decision logs live in their own docs — `L1_Ingestion.md`, `L2_Query_Pipeline.md`, and `L3_Presentation.md` — and the working method and decision history are in `Project_Working_Charter.md`. Read this for the shape of the whole; read those for the *why* behind each choice.

> **Rewritten to reflect the settled Layer 1 and Layer 2 designs.** Two things changed materially from the first draft of this overview: (1) embedding is now a **hosted Pinecone Inference** model (`llama-text-embed-v2` @ 384-dim), not a locally-run `all-MiniLM-L6-v2`; and (2) the online query service runs on an **always-warm AWS Lightsail VPS behind Cloudflare**, not AWS Lambda. Ingestion alone stays on Lambda + EventBridge. The layer model has also been reconciled (see note below).
>
> **Updated again for the settled Layer 3 design.** Layer 3 (Presentation / Frontend) is now fully designed — an **inline, first-party React widget** consuming the SSE contract. Its section below reflects the settled design rather than a placeholder, and "Where this sits in the project" has been updated accordingly. Layer 3's design produced **no backward ripples** into Layers 1–2 except one clarification: Layer 2's CORS allowlist must include both the local dev origin (Phase 2) and the production origin (Phase 3).

---

## The mental model: two pipelines

A RAG system is really **two pipelines that run at different times**:

- **Offline pipeline** — runs ahead of time, on a schedule. It prepares the knowledge base. (Layer 1)
- **Online pipeline** — runs per user request, in real time, when someone asks a question. (Layers 2–3)

The two pipelines never run together, but they are joined at a single seam: they must embed text using the **exact same model**, or retrieval breaks. That shared component is what makes the whole system coherent (see *Cross-cutting concerns*).

The layers, from foundation upward:

| Layer | Name | Runs when | Responsibility |
| --- | --- | --- | --- |
| 1 | Offline Ingestion Layer | Scheduled (offline) | Turn Notion content into searchable vectors |
| 2 | Query Pipeline & Serving Layer | Per request (online) | The RAG logic (retrieve + generate) **and** the HTTP API that exposes it |
| 3 | Presentation / Frontend Layer | Per request (in the browser) | The React chat widget the visitor interacts with |

Layer 1 is the foundation: nothing downstream works until the vector store is populated. Layers 2–3 then stack on top.

> **Note on the layer model.** An earlier draft of this overview split "Query Pipeline" and "API / Serving" into two separate layers. In the detailed design they were settled together — the API contract, hosting, streaming transport, and abuse control are all part of the Query Pipeline doc (`L2_Query_Pipeline.md`). So this overview folds serving into **Layer 2** and numbers the React widget as **Layer 3**, matching the working charter. The RAG-logic-vs-transport separation is still architecturally real (see Layer 2 below); it's just designed as one layer rather than two.

---

## Layer 1 — Offline Ingestion Layer

**Responsibility:** Read curated content from Notion, transform it into vector embeddings, and store it in a vector database ready for semantic search.

**Runs when:** Offline, on a schedule (manual → nightly cron → EventBridge), independently of any user.

**Components:**

- **Notion API** — fetches pages from a dedicated `Portfolio` section; `last_edited_time` drives incremental sync.
- **Chunker** — splits page text into ~500-token chunks with ~50-token overlap. (Input length confirmed for the working-choice model: `llama-text-embed-v2` accepts 2048 tokens and Pinecone recommends 400–500, so ~500-token chunks are well within range.)
- **Embedding — hosted Pinecone Inference** — each chunk is embedded via the Pinecone embed endpoint (working choice `llama-text-embed-v2` @ **384-dim**), with `input_type=passage`. No local model, no `torch`.
- **Vector store** — Chroma (local dev) / Pinecone (production); stores vector + chunk text + metadata (page ID, title, `last_edited_time`, chunk position, and a public `url`/slug + optional `anchor` for source links).

**Key property:** This layer produces the *only* data the rest of the system reads. Its output — a populated vector store — is the contract every other layer depends on.

*(Full design, decisions log, and deployment phases: `L1_Ingestion.md`.)*

---

## Layer 2 — Query Pipeline & Serving Layer

**Responsibility:** The RAG logic itself — given a question, retrieve the most relevant chunks and generate a grounded answer — **plus** the HTTP API that exposes it. The mirror image of ingestion, run online per request.

**Runs when:** Per request, online.

**The RAG logic — four stages:**

1. **Embed the query** — converted to a 384-dim vector via the **same hosted Pinecone model** used in Layer 1, with `input_type=query`. Mandatory: query and chunk vectors must share a space for cosine similarity to mean anything.
2. **Vector similarity search** — cosine similarity, top-**k = 4** (tunable, calibrated in Phase 1). A **hybrid relevance gate** sits here: if nothing clears a similarity threshold, short-circuit with a bare canned decline and never call the LLM (cheap, hallucination-proof, injection-resistant).
3. **Prompt construction** — retrieved chunks (source-tagged, best-match-first) + the question go in the *user* message; a static **system prompt** enforces third-person framing, grounding ("answer only from context"), a bare-but-polite decline, and injection resistance. Single-turn (no history).
4. **LLM generation** — sent to **Claude Haiku 4.5** (Anthropic Messages API), streamed token-by-token, low temperature, capped output. The smallest current model is plenty for grounded extractive QA.

**The serving half (transport — conceptually distinct from the RAG logic):**

- **FastAPI endpoint** — `POST /v1/ask`, single stateless route; question validated and length-capped.
- **Server-Sent Events** — typed `sources` → `delta`s → `done` stream; `429` before the stream for rate limits; `error` event for graceful failures; CORS locked to the site origin (must include both the dev origin in Phase 2 and the production origin in Phase 3 — see Layer 3).
- **Hosting** — runs on an **always-warm AWS Lightsail VPS** (under a process manager) so the SSE connection streams natively — no Lambda buffering or adapters. **Cloudflare** sits in front for DNS, TLS, DDoS, and edge rate limiting.

**Key property:** Small in code but where the hard design decisions live — relevance gating, prompt design, streaming transport, failure handling. Keeping the RAG logic conceptually separate from serving means it can be tested as a plain CLI (Phase 1) before any web server exists.

*(Full design, decisions log, API contract, and deployment phases: `L2_Query_Pipeline.md`.)*

---

## Layer 3 — Presentation / Frontend Layer

**Responsibility:** The interface the visitor actually touches — the "ask me anything" chat a recruiter sees and uses.

**Runs when:** Per request, online (in the visitor's browser).

**Components:**

- **React chat widget** — an **inline panel**, built as a **first-party client component** (`'use client'`) inside the existing Next.js site (no embed bundle, no iframe). Captures the question, calls the Layer 2 `POST /v1/ask` endpoint, and consumes the SSE stream with a **hand-rolled `fetch` + manual parser** (native `EventSource` is GET-only and can't carry the POST body). Renders the answer token-by-token as plain text, driven by a typed `useReducer` state machine (`idle → submitting → streaming → done | error`). Shows source cards from the `sources` event — grouped by page title, with a compact preview + ellipsis — and "read more →" links that activate once the public portfolio pages exist (`url` is nullable until then). Accumulates a discrete-pairs transcript for the session (each call independent — single-turn is preserved).

**Design highlights:** hybrid error handling (429 caught *pre-stream*; a mid-stream error keeps the partial answer; time-to-first-event timeout only, never a duration cap); accessibility via a hidden `aria-live="polite"` region that announces the *completed* answer (the visible stream is deliberately **not** the live region); style isolation via CSS Modules + a root reset, with the widget owning an overridable CSS-custom-property palette; ships through the existing GitHub Action → Azure pipeline and holds **no secrets** (Pinecone/Anthropic keys stay server-side on Lightsail).

**Status:** designed. Full design, decisions log, and implementation checklist: `L3_Presentation.md`.

**Still separate / future work** (deliberately *not* folded into Layer 3):

- The **public portfolio content pages** — the "C2" work the source links depend on (building real pages + populating each chunk's `url` at ingestion). Until then the widget shows inline snippets and the links stay inert.
- **Operational concerns** (observability, cost monitoring, answer-quality evaluation), earmarked as a future **Layer 4**. The widget's `useReducer` dispatch point is pre-positioned as the client-side hook for that work, so nothing needs retrofitting.

**Key property:** The only layer the end user perceives. Everything beneath — retrieval, augmentation, generation, serving — is invisible.

---

## Cross-cutting concerns

**The shared embedding model (the seam between Layer 1 and Layer 2).**
Both pipelines must embed text with the **same hosted Pinecone model** (working choice `llama-text-embed-v2` @ 384-dim) into the same space — `input_type=passage` when ingesting, `input_type=query` when querying. If the model ever changes, the entire corpus must be re-embedded, or cosine similarity becomes meaningless. The index is configured for **cosine** at **384 dimensions** to match. This single shared component stitches the two pipelines together.

**The API contract (the seam between Layer 2 and Layer 3).**
Where Layers 1–2 meet at a single deep component (the embedding model), Layers 2–3 meet at a *wide, shallow* surface: the SSE contract. Many small clauses — POST-with-body (privacy), typed `sources`/`delta`/`done`/`error` events, sources-first ordering, decline-through-the-stream, 429-before-stream, nullable `url` — each determine a piece of the widget. Several were deliberately shaped *for* the widget during Layer 2's design (sources-first so they can render during generation; nullable `url` so the widget isn't blocked on C2; decline-through-the-stream so the widget keeps one code path). Consuming the contract produced no change to it — though it surfaced one consequence of sources-first ordering: a *prompt-side* decline streams its sources before the model declines, so the widget shows source cards above a refusal. Handled at the display layer (an honest provenance label rather than a causation one), not by a contract change; a machine-readable decline signal was considered and deferred pending Phase-1 frequency data.

**Content scope as a safety boundary.**
The `Portfolio` section in Notion is the inclusion boundary set in Layer 1, but its effect is system-wide: nothing outside it can ever surface in an answer, because it was never embedded. Curation at ingestion time is the primary control on what the system can say. **The boundary holds on *removal*, not just addition:** Layer 1's mark-and-sweep reconcile deletes the chunks of any page moved out of Portfolio or deleted in Notion on the next sync, so de-curating a page actually removes it from what the system can retrieve (an earlier version of the design keyed only on edit timestamps and would have left such chunks orphaned and still retrievable — closed in `L1_Ingestion.md`). The hybrid relevance gate and prompt-side grounding are the secondary controls (don't answer what isn't in the retrieved context). *(The same removal boundary is what makes the build-time synthetic seed fully swappable at launch — moving the synthetic pages out of Portfolio sweeps their chunks; see `M4.2-03`.)*

**Environment progression.**
The vector store evolves from Chroma (local dev) to Pinecone (production). Embedding is hosted from day one (Pinecone Inference), so even local dev calls the Pinecone embed API and stores the returned vectors in Chroma. Hosting splits by layer: **ingestion on Lambda + EventBridge** (a batch job, cold starts irrelevant), **query on Lightsail + Cloudflare** (always-warm, streaming), **frontend through the existing GitHub Action → Azure pipeline** (a first-party component in the Next.js site — no separate hosting). The layers sensibly run on different services.

**Cost (whole system, portfolio scale).**
Hosted embedding sits inside Pinecone's free tier; the Pinecone vector store free tier covers a small corpus; Claude Haiku API is billed separately from any Claude subscription (~$0.003/query); Lightsail is a flat ~$3.50–5/mo; Cloudflare's relevant features are free. The frontend adds **no incremental cost** — it ships through the existing Azure pipeline and holds no secrets. All-in: a few dollars a month.

---

## End-to-end data flow

```
                    ┌─────────────────────────────────────────────┐
   OFFLINE          │  LAYER 1 — INGESTION                         │
   (scheduled,      │                                              │
    on Lambda)      │  Notion API                                  │
                    │      ↓  (fetch /Portfolio pages)             │
                    │  Chunker (500 tok, 50 overlap)               │
                    │      ↓                                       │
                    │  Pinecone Inference embed  ──► 384-dim       │
                    │   (llama-text-embed-v2, input_type=passage)  │
                    │      ↓                                       │
                    │  Vector Store (Chroma dev / Pinecone prod)   │
                    └───────────────────────┬─────────────────────┘
                                             │  (populated store)
   ══════════════════════════════════════════════════════════════
                                             │
                    ┌────────────────────────▼─────────────────────┐
   ONLINE           │  LAYER 3 — PRESENTATION                      │
   (per request)    │  React chat widget — inline panel            │
                    │  (first-party component; visitor asks)       │
                    └───────────────────────┬─────────────────────┘
                                             │  HTTP POST /v1/ask
                                             │  (SSE response)
                    ┌────────────────────────▼─────────────────────┐
                    │  LAYER 2 — QUERY PIPELINE & SERVING          │
                    │  Cloudflare (TLS, DDoS, edge rate limit)     │
                    │      ↓                                       │
                    │  FastAPI on AWS Lightsail (always-warm)      │
                    │   1. Embed query (Pinecone, input_type=query)│
                    │   2. Cosine top-k=4  +  relevance gate  ◄─ same
                    │   3. Prompt construction (3rd-person, ground)│  model
                    │   4. Claude Haiku 4.5 (streamed)             │
                    └───────────────────────┬─────────────────────┘
                                             │  SSE: sources → deltas → done
                                             ▼
                              back up to Layer 3
                              → hand-rolled SSE parse → reducer
                              → rendered token-by-token in the widget
```

---

## Layer ownership & deployment summary

| Layer | Core tech | Phase 1 (local) | Phase 3 (cloud) |
| --- | --- | --- | --- |
| 1 — Ingestion | Python, `notion-client`, `pinecone`, `chromadb` | Manual script; embed via Pinecone API → Chroma | Lambda + EventBridge + Pinecone |
| 2 — Query pipeline & serving | Python, `fastapi`, `uvicorn`, `pinecone`, `anthropic` | CLI → FastAPI on localhost, against Chroma | Lightsail (always-warm) + Cloudflare, against Pinecone |
| 3 — Presentation / frontend | React (Next.js client component), hand-rolled SSE, CSS Modules | Widget → localhost API (no CLI phase; starts at Layer 2's Phase 2) | First-party component shipped via GitHub Action → Azure; widget → Cloudflare/Lightsail API |

*(Embedding is a hosted Pinecone API call in every phase — no `sentence-transformers` / `torch` anywhere. The frontend carries no SSE/state/markdown libraries — deliberately minimal; see `L3_Presentation.md`.)*

---

## Where this sits in the project

- **Designed:** Layer 1 (Ingestion), Layer 2 (Query Pipeline & Serving), and Layer 3 (Presentation / Frontend) — all fully specified, with decision logs. See `L1_Ingestion.md`, `L2_Query_Pipeline.md`, `L3_Presentation.md`.
- **Separate future tasks (scoped, not yet designed):** the **public portfolio content pages** (C2 — real pages + populating each chunk's `url` at ingestion, which activates the widget's source links); and a future **Layer 4** for operational concerns (observability, cost monitoring, answer-quality evaluation).
- **Build-time content strategy:** the system is built and calibrated on a **shape-matched synthetic persona**, with a launch-gate swap to real content (`M4.2-03`) before public exposure — keeping real authoring off the build's critical path. The mark-and-sweep reconcile makes the swap a content-only operation (out-of-scope synthetic pages are swept). *(See `Placeholder_Content_Restructure.md`.)*
- **Then:** implementation, following each layer's local → automated → cloud phasing. The design across all three layers is intentionally settled *before* coding begins.

*(Working method, conventions, and the full settled-decision snapshot: `Project_Working_Charter.md`.)*
