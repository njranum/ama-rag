# Implementation Tickets — Generation Record

> Companion to the layer design docs (`L1_Ingestion.md`, `L2_Query_Pipeline.md`, `L3_Presentation.md`) and the `Project_Working_Charter.md`. This documents the one-time exercise that converted the settled Layer 1–3 design into a concrete, executable backlog in Notion. It records **what** the action items are, **how** they were generated, and confirms they are **live** in the workspace — created as real Notion pages, not held as a draft.

---

## 1. What the action items are

**41 implementation tickets** in the **DB Action Items** Notion database, each linked (via a relation) to the RAG portfolio project. They are the bridge between the finished design ("every necessary decision made, reasoned, recorded") and execution. Nothing in them re-opens a design decision; they translate decisions already settled in the layer docs into ordered, buildable work.

They are organised into **five milestones** that map onto the architecture's layers plus the cloud rollout:

| Milestone | Scope | Maps to |
| --- | --- | --- |
| **M0 — Foundations & Setup** | Accounts, credentials, repo, dependency baseline, model lock | Cross-cutting prerequisites |
| **M1 — Ingestion** | Notion fetch → chunk → embed → store; sync + reconcile; local cron | Layer 1 (Phase 1–2) |
| **M2 — Query Pipeline** | CLI retrieval + gate; threshold calibration; prompt + generation; FastAPI + SSE | Layer 2 (Phase 1–2) |
| **M3 — Frontend Widget** | Scaffold; SSE parser; state machine; rendering; sources; interaction; errors; a11y; styling | Layer 3 (Phase 2) |
| **M4 — Cloud Deployment & Launch** | Lightsail + Cloudflare; Pinecone prod; Lambda + EventBridge; ship widget; end-to-end verify; scoped future work | All layers, Phase 3 (+ C2 / Layer 4) |

The milestone count was capped at five because the Notion `Milestone` select only had five slots; the layer-to-milestone mapping was designed to fit that cleanly rather than forcing a schema change there.

### Anatomy of a ticket

Every ticket carries a consistent set of **properties**:

- **Name** — `M{X}.{Y}-{NN} — {Title}` (Milestone.Slice-Number, em-dash, imperative title), matching the existing convention already in the database.
- **Milestone** — M0–M4.
- **Area** — `Notion`, `Infra`, `Ingestion`, `Query Pipeline`, or `Frontend` (the last three were added for this project — see §3).
- **Priority** — High / Medium / Low.
- **Type** — `Research / Claude` on tickets Claude executes; left blank on purely-manual tickets (see below).
- **Project** — a relation linking the ticket to the RAG project page.
- **Status** — all created as `Not started`.
- **Req IDs** — a free-text trace back to the originating design decision (e.g. `L2: API contract; Retrieval`, `L3: D5`), so any ticket can be read against the doc that justifies it.

And a consistent **body** structure, written to a depth an executing agent (or a developer) can act on without re-reading the design docs:

- **Slice** — the sub-grouping the ticket belongs to.
- **What** — the concrete deliverable.
- **Why** — the reasoning, carried from the design doc so the rationale travels with the work.
- **Steps** — the actual implementation steps.
- **Verify** — how to confirm it's done correctly.
- **Common issues** — the traps recorded during design (e.g. the 1024-dim default, the SSE cross-chunk buffering bug, Cloudflare buffering `text/event-stream`).

### Manual vs Claude-executed

Five tickets are **purely manual** (account setup, content authoring, and a live screen-reader test) and are deliberately left untyped to distinguish them from work Claude can do:

- **M0.1-01** — Set up Notion integration + share Portfolio section
- **M0.2-01** — Create Pinecone account + API key
- **M0.3-01** — Set up Anthropic API access + billing credits
- **M1.1-01** — Author Portfolio content in Notion + pre-ingestion audit
- **M3.6-02** — Live screen-reader test (VoiceOver + NVDA)

Everything else is tagged `Research / Claude`.

---

## 2. How they were generated (the method)

The generation followed the same deliberate method the design itself used (per the Working Charter), applied to backlog-building rather than decision-making:

1. **Source of truth was the design docs, not memory.** The tickets were derived from the four settled documents — the three layer docs plus the architecture overview — so each ticket reflects a decision already made and recorded, with its Req-ID pointing back to it.

2. **Milestone ≈ layer, with phasing preserved as progression.** The layers' local → automated → cloud phasing was preserved by pushing all Phase-3 (cloud) work into **M4**, so M1–M3 are buildable and testable locally before any cloud infrastructure exists. This keeps the "prove it locally first" discipline intact at the backlog level.

3. **Decompose each layer into slices, then tickets.** Each layer was broken into its natural slices (e.g. M2's *Query CLI*, *Threshold calibration*, *Prompt & generation*, *FastAPI + SSE serving*), and each slice into one or more tickets sized to a single coherent piece of work.

4. **Write to executable depth.** Rather than one-line task names, each ticket got the full What/Why/Steps/Verify/Common-issues body, with the *why* and the *common issues* lifted from the design docs so the reasoning and the known traps travel with the work.

5. **Trace every ticket to a decision.** The Req-IDs scheme ties each ticket back to the specific design decision(s) it implements, keeping the "reasoning is the deliverable" thread unbroken from design into execution.

6. **Surface cross-milestone dependencies explicitly.** The backlog is not strictly linear, and the non-obvious dependencies were called out in the tickets and the handover (e.g. M2.4-03 sequences after the M3 scaffold; M3.4-01's chips come from M2.2-01's eval set; M0.5-01's model lock gates M1.2-01's index; M4.4-01's CORS depends on M2.4-01).

7. **Defer, don't drop.** The future-scoped work was recorded as explicit Low-priority placeholder tickets (M4.5-01 for the C2 public pages, M4.5-02 for Layer 4 operational concerns), clearly marked `[Future]`, so it isn't lost but also isn't mistaken for build-now scope.

8. **Upload in chunks, verifying as we went.** Tickets were created one milestone at a time. After the first milestone (M0) the result was fetched back and inspected to confirm the body rendered, the Area tagged correctly, and — importantly — the **Project relation actually linked** rather than being stored as raw text. Once the format was confirmed, the remaining milestones were created in batches.

---

## 3. Were they live?

**Yes — all 41 were created live as real Notion pages in the DB Action Items database, not drafted or staged.** Specifics of the live write:

- **41 pages created**, each with all properties populated and the full structured body, across five batched create operations (one per milestone). Every batch returned successfully with no errors.
- **The Project relation links correctly.** This was the main thing verified after the first batch: the relation resolves to the RAG project page rather than sitting as a text string.
- **One live schema change was required first.** The initial M0 create attempt **failed** because the Notion API does not auto-create new select options — the three project-specific `Area` values (`Ingestion`, `Query Pipeline`, `Frontend`) didn't exist yet. The data source schema was updated live to add them (with colours purple / pink / red), **preserving every existing option** so the other project sharing this database (its `Main Process` / `Renderer` / `Both` Area values) was untouched. The M0 create then succeeded on retry. This is the one and only modification made to the shared database structure.
- **Statuses** are all `Not started`, ready to be worked.
- **The work is browsable in Notion now** — each ticket is a live page in DB Action Items, filterable by Milestone, Area, and Priority, and linked back to the RAG project.

So the answer to "were they live" is unambiguous: the action items are not a proposal or an export — they are live, populated, project-linked Notion pages, and the database's schema was extended live (with prior approval) to hold them.

---

## 4. The backlog (ticket index)

### M0 — Foundations & Setup
| Ticket | Title | Area | Priority | Who |
| --- | --- | --- | --- | --- |
| M0.1-01 | Set up Notion integration + share Portfolio section | Notion | High | Manual |
| M0.2-01 | Create Pinecone account + API key | Infra | High | Manual |
| M0.3-01 | Set up Anthropic API access + billing credits | Infra | High | Manual |
| M0.4-01 | Initialise repo + Python env + dependency baseline | Infra | High | Claude |
| M0.5-01 | Lock embedding model + dimension | Ingestion | High | Claude |

### M1 — Ingestion (Layer 1)
| Ticket | Title | Area | Priority | Who |
| --- | --- | --- | --- | --- |
| M1.1-01 | Author Portfolio content in Notion + pre-ingestion audit | Notion | High | Manual |
| M1.2-01 | Create Pinecone index (384-dim, cosine) + verify vector length | Infra | High | Claude |
| M1.3-01 | Notion fetch: enumerate Portfolio subtree + extract text/metadata | Ingestion | High | Claude |
| M1.4-01 | Chunker (~500 tokens, ~50 overlap, chunk position) | Ingestion | High | Claude |
| M1.5-01 | Embed (input_type=passage) + store to Chroma with metadata | Ingestion | High | Claude |
| M1.6-01 | Incremental sync + delete-before-upsert | Ingestion | Medium | Claude |
| M1.6-02 | Mark-and-sweep reconcile (removal boundary) | Ingestion | Medium | Claude |
| M1.7-01 | Stamp nullable source url/slug + anchor metadata | Ingestion | Medium | Claude |
| M1.8-01 | Local nightly cron (Phase 2) | Infra | Low | Claude |

### M2 — Query Pipeline (Layer 2)
| Ticket | Title | Area | Priority | Who |
| --- | --- | --- | --- | --- |
| M2.1-01 | Query CLI: embed query + cosine top-k=4 + score normalisation | Query Pipeline | High | Claude |
| M2.1-02 | Hybrid relevance gate + canned decline (no LLM call) | Query Pipeline | High | Claude |
| M2.2-01 | Build Phase-1 eval set (should-answer / should-refuse) | Query Pipeline | Medium | Claude |
| M2.2-02 | Calibrate threshold + record config + sources-then-decline rate | Query Pipeline | High | Claude |
| M2.3-01 | Prompt construction: system prompt + source-tagged context | Query Pipeline | High | Claude |
| M2.3-02 | Generation: Haiku 4.5 streamed, low temp, capped, fallback | Query Pipeline | High | Claude |
| M2.4-01 | FastAPI POST /v1/ask: validation, 500-char cap, CORS allowlist | Query Pipeline | High | Claude |
| M2.4-02 | SSE stream: sources/delta/done/error + 429 pre-stream | Query Pipeline | High | Claude |
| M2.4-03 | Wire widget to local API + dev/prod query-path note | Query Pipeline | Medium | Claude |

### M3 — Frontend Widget (Layer 3)
| Ticket | Title | Area | Priority | Who |
| --- | --- | --- | --- | --- |
| M3.1-01 | Scaffold 'use client' inline widget + env config | Frontend | High | Claude |
| M3.1-02 | Hand-rolled fetch + SSE parser (4 obligations) | Frontend | High | Claude |
| M3.2-01 | useReducer state machine (idle/submitting/streaming/done/error) | Frontend | High | Claude |
| M3.2-02 | Plain-text pre-wrap streaming + discrete-pairs transcript | Frontend | High | Claude |
| M3.3-01 | Source cards: render-on-arrival, group-by-title, provenance label | Frontend | Medium | Claude |
| M3.4-01 | Interaction: suggested-question chips + input defaults | Frontend | Medium | Claude |
| M3.5-01 | Error & resilience: TTFB timeout, keep-partial, retry, abort | Frontend | Medium | Claude |
| M3.6-01 | Accessibility: hidden live region + announce-on-complete + checklist | Frontend | High | Claude |
| M3.6-02 | Live screen-reader test (VoiceOver + NVDA) | Frontend | Medium | Manual |
| M3.7-01 | Styling: CSS Modules + root reset + palette + AA/motion/dark | Frontend | Medium | Claude |

### M4 — Cloud Deployment & Launch
| Ticket | Title | Area | Priority | Who |
| --- | --- | --- | --- | --- |
| M4.1-01 | Provision Lightsail VPS + process manager + deploy FastAPI | Infra | High | Claude |
| M4.1-02 | Cloudflare in front (DNS/TLS/DDoS) + edge rate-limit | Infra | High | Claude |
| M4.2-01 | Switch prod vector store to Pinecone + integrated inference | Infra | High | Claude |
| M4.2-02 | Deploy ingestion as Lambda + EventBridge nightly | Infra | Medium | Claude |
| M4.3-01 | Ship widget via GitHub Action → Azure + set prod API URL | Frontend | High | Claude |
| M4.4-01 | End-to-end prod verification (SSE through Cloudflare, CORS) | Infra | High | Claude |
| M4.5-01 | [Future · C2] Public portfolio pages + populate per-chunk url | Frontend | Low | Claude |
| M4.5-02 | [Future · Layer 4] Observability, cost + answer-quality eval | Infra | Low | Claude |

*(Each ticket's full body and its live Notion page link are in the DB Action Items database.)*

---

## 5. Notes carried into the backlog

- **One genuinely open decision remains, flagged in M0.5-01:** the final embedding-model lock. `llama-text-embed-v2` @ 384-dim is the working choice (input length confirmed at 2048 tokens), with `multilingual-e5-large` @ 1024 recorded as the alternative and the 1024-default trap flagged for verification at lock time.
- **Sequencing is not strictly linear.** The cross-milestone dependencies above (M2.4-03 ↔ M3.1; M3.4-01 ↔ M2.2-01; M0.5-01 → M1.2-01; M4.4-01 ↔ M2.4-01) should be honoured when ordering work, rather than working each milestone top-to-bottom in isolation.
- **Future work is parked, not lost.** C2 (public portfolio pages, which activate the widget's source links) and Layer 4 (operational concerns) exist as explicit `[Future]` tickets so they remain visible without being mistaken for launch-blocking scope.