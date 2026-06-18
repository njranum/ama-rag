# RAG Portfolio Project — Working Method & Decision Charter

> This is the working-method companion to the per-layer architecture docs (Ingestion Layer, Query Pipeline Layer, and Presentation Layer). It documents *how* we design this project and *what* we are trying to get out of the exercise, so any new thread can pick up the work with full context and continue in the same style. Read this first, then the layer docs.

---

## 1. What this document is

The project is being designed **collaboratively, one decision at a time**, through a back-and-forth between Nic (project owner) and Claude. We work through a layer, decompose it into the decisions hiding inside it, and talk each one through — options, trade-offs, a recommendation, a choice — until the layer is fully specified. The output of each layer is a standalone architecture-and-decisions document.

This charter exists because the *method* is deliberate and worth preserving: the quality of the project comes from the reasoning, not just the final stack. A new thread that understands the method can continue seamlessly; one that doesn't will produce shallower work.

**How to use this in a new thread:** read this charter, then the existing layer docs (they carry the settled decisions and their rationale). Then continue the same decision-by-decision method on the next open layer. Expect to revise earlier docs as new decisions ripple backwards (see §3).

---

## 2. The project (self-contained context)

Nic is building a **Retrieval-Augmented Generation (RAG) system as a portfolio piece** for a London job search. The end product is an **"ask me anything" chat widget embedded on Nic's personal website**, where recruiters and visitors can ask questions about Nic's professional background and get conversational, grounded answers.

Defining characteristics:

- **Third person, not impersonation.** The assistant answers *about* Nic ("Nic has experience in…"), never *as* Nic.
- **Curated, safe content scope.** Only a dedicated `Portfolio` section of Nic's Notion workspace is indexed, so private notes are never exposed by default.
- **The reasoning is the deliverable.** Because this is a portfolio artifact, *demonstrating considered, defensible engineering decisions* matters as much as the running system. "I reasoned through each layer" is the value; "I clicked together a managed service" is not.
- **Pragmatic and phased.** Avoid premature infrastructure. Build locally first, add automation, then cloud — only when each step is justified.

Nic's background informs choices: prior experience with React and AWS (a chess-stats app), comfort with a VPS-style setup, and a multi-cloud reality (personal site on Azure, DNS on Cloudflare).

---

## 3. How we work (the method)

This is the core of the charter. The pattern that has worked:

**Decompose before deciding.** When we open a layer, we first lay out *all* the decisions hiding inside it — including the non-obvious ones — so both sides see the shape of the work before diving in. Then we sequence them sensibly (usually following the data flow, hardest-or-most-foundational first).

**One decision at a time.** We don't try to settle everything at once. Each decision gets its own focused exchange. When a list of choices would overwhelm, Claude separates **the one decision that needs real thought** from the **mechanical defaults** it can just propose for a yes/no.

**Claude's role per decision:** lay out the genuine options, give the honest trade-offs, and state a clear recommendation (a "lean") with reasoning — not a neutral menu. Claude should have an opinion and defend it, while leaving the call to Nic.

**Nic's role:** react, choose, redirect, or push back. Reacting to a concrete proposal is easier than specifying from scratch — so for design-heavy items (system prompt, API contract), Claude drafts something concrete and Nic reacts to it, rather than discussing in the abstract.

**Verify current facts, don't rely on memory.** Anything that changes over time — pricing, free tiers, product availability, model names, platform capabilities — gets checked against current sources before it informs a decision. (This has already changed outcomes: App Runner turning out to be closed to new customers; API Gateway gaining streaming; the AWS public-IPv4 charge; Pinecone not hosting the originally-chosen model; the current SSE-over-fetch library landscape and ARIA-live behaviour for streaming.)

**Pragmatism over completeness — "note and defer."** When something is real but unnecessary at portfolio scale (re-ranking, metadata pre-filtering, prompt caching, jump-to-passage links, shadow-DOM isolation, a markdown renderer, true multi-turn), we record it as deliberately deferred with the reason, rather than building it or pretending it doesn't exist. This keeps scope honest and avoids premature engineering.

**Decisions ripple across layers — expect to revise.** This is the most important meta-lesson. Settling a decision in one layer frequently invalidates or reshapes an earlier one. The docs are **living**: when a later choice changes an earlier rationale, we go back and update the affected doc.
- *Example (deep ripple):* the Layer 2 decision to host embedding was originally justified by "torch cold-starts on Lambda." Later, the hosting decision moved the query service off Lambda to an always-warm VPS — which made the cold-start argument moot. We kept the original reasoning for history and annotated it with a "superseded, decision unchanged" note explaining the new (cost-based) justification.
- *Counter-example (shallow seam):* Layer 3 consumed the Layer 2 API contract without forcing any change back into it — every backward-ripple check (error codes, contract shape, keepalive) came back clean except one small clarification (CORS must allow both the dev and prod origins). A well-drawn boundary ripples wide but not deep.

**Intellectual honesty about reasoning.** When the *why* behind a decision stops being true, we say so plainly rather than letting a doc justify a right call with a dead argument. We keep the history and annotate it; we don't quietly rewrite it. Claude is expected to flag these even when unprompted.

**Keep a clean record as we go.** Decisions are written into the layer doc as they're made, with the decision, the rationale, the rejected alternatives, and any deferrals. Working choices (not yet locked) are labelled as such.

---

## 4. What we produce

**One architecture-and-decisions document per layer**, following a consistent structure so the set reads as a coherent whole:

1. **Overview** — what the layer does, when it runs, a status note.
2. **Architecture: How It Works** — the stages, with an ASCII pipeline diagram.
3. **Deployment Phases** — the local → automated → cloud progression for that layer.
4. **Decisions Log** — per decision: the decision, rationale, rejected alternatives, and deferred items. Superseded reasoning is annotated, not deleted.
5. **Open Decisions** — what's still unsettled, shrinking as we go; settled items summarised.
6. **Libraries & Dependencies.**
7. **Open Questions / Next Steps** — the implementation checklist.

Cross-layer impacts are flagged inline (e.g. "Layer 1 must be updated to…") so nothing is lost when a decision reaches across layers.

---

## 5. What we want to get out of it

- **A complete, internally-consistent design across all layers, settled *before* implementation begins.** We are intentionally front-loading the thinking so that writing code is execution, not discovery.
- **Documented, defensible reasoning** for every non-trivial choice — the portfolio value, and the thing that lets a future reader (or interviewer, or new thread) understand *why*, not just *what*.
- **A phased implementation plan** per layer, so building can start small and locally and grow into cloud only as justified.
- **Continuity across threads.** Because this spans many sessions, the docs + this charter are the shared memory. Each session leaves the design more complete and the docs consistent.

The finish line is not "code written" — it's "every necessary decision made, reasoned, recorded, and consistent across layers, such that implementation is unambiguous." **All three layers are now at that line.**

---

## 6. Ground rules / conventions

- **Working choice vs locked decision** — label anything not yet final (e.g. the embedding model is a "working choice": `llama-text-embed-v2` @ 384, strategy locked, exact model open).
- **Phasing pattern** — every layer uses local → automated → cloud, mirroring the others (Layer 3 starts at Phase 2, since the CLI phase predates any UI).
- **Cross-layer notes** — when a decision affects another layer, write the impact into both docs.
- **Defer, don't drop** — premature complexity is recorded as a deliberate deferral with a reason.
- **Verify before asserting** — current-state facts are searched, not recalled.
- **Honesty over tidiness** — keep superseded reasoning visible and annotated.

---

## 7. Layer map & current status

- **Layer 1 — Ingestion Layer** — ✅ designed, then revised. Pulls the Notion `Portfolio` section, chunks (~500 tokens / ~50 overlap), embeds via hosted Pinecone Inference, stores in Chroma (dev) / Pinecone (prod). Runs as a scheduled batch job on Lambda + EventBridge. *(See `L1_Ingestion.md`.)*
- **Layer 2 — Query Pipeline Layer** — ✅ designed (all stages + infra settled). Embed query → cosine top-k retrieval with a hybrid relevance gate → grounded third-person prompt → Claude Haiku 4.5, streamed → FastAPI on an always-warm Lightsail VPS behind Cloudflare. *(See `L2_Query_Pipeline.md`.)*
- **Layer 3 — Presentation / Frontend Layer** — ✅ designed. An **inline, first-party React widget** (`'use client'`) in the existing Next.js site: hand-rolled `fetch` + manual SSE parser (native `EventSource` can't carry a POST body), typed `useReducer` state machine, plain-text token streaming, source cards (grouped by title, preview + ellipsis, conditional `read more →`), discrete-pairs transcript, hybrid error handling (429 pre-stream; keep partial answer on mid-stream error; time-to-first-event timeout), hidden-`aria-live` announce-on-complete accessibility, and CSS Modules + root reset with an overridable custom-property palette. Ships via the existing GitHub Action → Azure; holds no secrets. *(See `L3_Presentation.md`.)*
- **Separate future tasks (scoped, not designed):**
  - **C2 — public portfolio content pages.** Build real pages and populate each chunk's `url` at ingestion; this activates the widget's "read more →" source links (inert until then). A content/site-architecture task plus a small Layer 1 change.
  - **Layer 4 — operational concerns.** Observability, cost monitoring, answer-quality evaluation. Mostly server-side/cross-cutting; the widget's `useReducer` dispatch point is pre-positioned as the client-side hook, so nothing needs retrofitting.

---

## 8. Current architecture snapshot (the settled through-line)

A quick reference of what's decided across layers, so a new thread sees the spine without re-reading everything:

- **Source:** Notion API, scoped to a `Portfolio` section (full subtree — working choice); incremental embed via `last_edited_time` **plus a mark-and-sweep reconcile** each run (deletes chunks of pages moved out / deleted, and delete-before-upsert on changed pages — so the inclusion boundary holds on removal, and the vector store is its own sync state).
- **Chunking:** ~500 tokens, ~50 token overlap.
- **Embedding:** hosted **Pinecone Inference** (working choice `llama-text-embed-v2` @ **384-dim**; input length confirmed — 2048-token limit, ≫ ~500-token chunks; mind the 1024-dim default), same model for chunks (`input_type=passage`) and queries (`input_type=query`).
- **Vector store:** Chroma (local dev) / Pinecone (prod).
- **Retrieval:** cosine, top-k = 4 (tunable), scores normalised higher-is-better; metadata (title, page ID, chunk position, nullable `url`/`anchor`) carried through.
- **Relevance handling:** hybrid gate — a conservative retrieval gate (canned decline, no LLM call) + prompt-level grounding as backstop; threshold calibrated in Phase 1.
- **Prompt:** single-turn; static system prompt (third-person, grounded, bare-but-polite decline, injection-resistant) + dynamic source-tagged context and question.
- **Generation:** **Claude Haiku 4.5** via Anthropic Messages API, streamed, low temperature, capped output. (API billed separately from any Claude subscription.)
- **API:** `POST /v1/ask`, SSE response (`sources` → `delta`s → `done`), 429 before stream for rate limits, CORS locked to the site origin (**both** the local dev origin in Phase 2 and the production origin in Phase 3).
- **Hosting:** query service on **AWS Lightsail** (always-warm VPS) with **Cloudflare** in front (DNS, TLS, DDoS, edge rate limiting); ingestion stays on **Lambda + EventBridge**.
- **Frontend:** inline, **first-party React widget** in the existing Next.js site — hand-rolled SSE consumption, `useReducer` state machine, plain-text streaming, source cards grouped by title with nullable "read more →" links, discrete-pairs transcript, announce-on-complete accessibility, CSS Modules + root reset with an overridable palette. Ships via the existing GitHub Action → Azure; holds no secrets. *(Layer 3 — see `L3_Presentation.md`.)*
- **Deferred (recorded, not built):** re-ranking, metadata pre-filtering, adjacent-chunk dedup, prompt caching, jump-to-passage source anchors; embed/iframe distribution, shadow-DOM isolation, a markdown renderer, a formal state-machine library (XState), true multi-turn conversation, click-to-expand source text, sentence-chunk screen-reader announcement, an explicit stop button; a machine-readable decline signal on the API contract (revisit only if Phase-1 shows the sources-then-decline case is frequent).

**One backward ripple from Layer 3 (actioned):** Layer 2's CORS allowlist must include both the local dev origin (`http://localhost:3000`, Phase 2) and the production site origin (Phase 3) — a clarification of the existing contract, noted in `L2_Query_Pipeline.md`. No other Layer 1/2 decision changed.

**Post-design cross-document review (actioned).** A whole-stack consistency pass after all three layers were settled surfaced two refinements, both worked through in the usual options-and-lean format and rippled into the affected docs:

- **Honest sources label (Decision A).** The *prompt-side* decline streams its `sources` event before the model declines, so the widget would show source cards above a refusal. Fixed at the display layer by switching from a causation-asserting label ("Based on:") to a provenance-asserting one (working choice "From Nic's portfolio:") — honest on every path, no decline detection, no contract change. The heavier machine-readable-decline-signal option is deferred pending a Phase-1 frequency measurement. *Rippled into:* `L3_Presentation.md` (Decisions 4–5, supersedes "Based on:"), `L2_Query_Pipeline.md` (gate interaction + Phase-1 measurement), `RAG_System_Architecture.md` (API-contract seam note).
- **Ingestion reconcile (Decision B).** Incremental sync keyed only on `last_edited_time` of pages *in* Portfolio, so removals (page moved out / deleted) and shrinking pages left orphaned, still-retrievable chunks — puncturing the "nothing outside Portfolio can surface" safety boundary. Fixed with a mark-and-sweep reconcile + delete-before-upsert, which also makes the vector store its own sync state (resolving Phase-3 Lambda statelessness). *Rippled into:* `L1_Ingestion.md` (Sync strategy supersede, Scope recursion definition, Phase 3, free-tier refresh), `RAG_System_Architecture.md` (safety-boundary claim now covers removal).

Both are refinements *within* already-settled layers, not reopenings — the three layers remain at the "settled before implementation" line. The cross-document review also retired the model-lock input-length risk (verified: `llama-text-embed-v2` accepts 2048 tokens) and refreshed two drifted external facts (Pinecone Starter limits; Lightsail IPv6-only vs IPv4 pricing).

**One open sub-decision carried as a working choice:** the Portfolio scope recursion depth (full subtree vs direct-children-only) — defaulted to full subtree with the pre-ingestion audit as the over-inclusion backstop; flip in `L1_Ingestion.md` if a more exposure-conservative boundary is wanted.

---

## 9. For the next thread — kickoff

1. Read this charter, then `L1_Ingestion.md`, `L2_Query_Pipeline.md`, and `L3_Presentation.md`.
2. The three design layers are complete. The remaining work is either **implementation** (follow each layer's local → automated → cloud phasing and the per-layer checklists) or one of the **scoped future tasks** (C2 content pages; Layer 4 operational concerns). Confirm with Nic which is being picked up.
3. If a new design layer/task is opened: decompose it into its decisions, sequence them, and work through them one at a time using the method in §3.
4. Produce any new layer doc in the established structure (§4).
5. When a decision ripples back into an earlier layer, update that doc and annotate any superseded reasoning.
6. The goal remains: settle and record every necessary decision, consistently across layers, before implementation.
