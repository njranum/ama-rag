## Overview

This page documents the agreed architecture for the **Ingestion Layer** (Layer 1) of the RAG personal portfolio project, along with the reasoning behind each key decision.

The ingestion layer is responsible for pulling content from Notion, transforming it into vector embeddings, and storing it in a vector database ready for semantic search at query time.

> **Revision note:** the embedding approach was changed during the Layer 2 (Query Pipeline) design. The original choice was `all-MiniLM-L6-v2` run locally; it is now a **hosted model via Pinecone Inference**. The driver was query-side cold starts — running `torch` in a query Lambda produced 20–30s cold starts on a public endpoint. Because the query and the chunks must be embedded by the *same* model, that decision propagates here. Full rationale lives in the Layer 2 document; the embedding decision below has been rewritten and the affected sections updated.

---

## Architecture: How It Works

The ingestion pipeline runs in three stages:

**Stage 1 — Fetch from Notion**

A Python script connects directly to the Notion API (no manual exports) and pulls all pages that live inside a dedicated `Portfolio` section of your Notion workspace. Any page in that section is considered indexable. The script uses `last_edited_time` to detect changes and skip unchanged pages on subsequent runs.

**Stage 2 — Chunk**

Each page's text content is split into overlapping chunks (approx. 500 tokens, ~50 token overlap). Chunking allows precise retrieval of relevant passages rather than entire documents, and keeps each chunk within the embedding model's input limit. **Input-length check — confirmed (verified at the working-model level).** `llama-text-embed-v2` accepts up to **2048 input tokens**, and Pinecone's own recommended chunk size for it is **400–500 tokens** — so the ~500-token chunks sit squarely in the model's intended range (the underlying NVIDIA model goes to 8192). This retires the original concern: `all-MiniLM-L6-v2` capped at 256 tokens and would have silently truncated these chunks to roughly half. (Re-confirm if the final model lock lands on a different model.)

**Stage 3 — Embed & Store**

Each chunk is sent to the **Pinecone Inference** embedding endpoint (hosted model — working choice `llama-text-embed-v2`, configured for **384-dimension** output), with `input_type` set to **`passage`**. The returned vector, plus the original chunk text and metadata (page ID, title, last edited time, chunk position, and a public `url`/slug — see below), is upserted into the vector store.

```
Notion API
    ↓  (fetch pages in /Portfolio section)
Chunker
    ↓  (500 token chunks, 50 token overlap)
Pinecone Inference embed  (llama-text-embed-v2, 384-dim, input_type=passage)
    ↓  (384-dimension vectors)
Vector Store  ←  Chroma (local dev) / Pinecone (production)
```

> **Embedding path by phase:** in local dev, call Pinecone's standalone embed endpoint and store the returned vectors in local Chroma. In production, Pinecone's *integrated inference* can embed and upsert in a single call. Either way the model and `input_type` are identical, so the vectors are interchangeable across phases.

---

## Deployment Phases

**Phase 1 — Local, manual**

- Script run manually from terminal
- Chunks embedded via the Pinecone Inference API; vectors stored in Chroma (local folder on disk)
- Requires a Pinecone API key and a Notion integration token; no other cloud infrastructure
- Used during development and testing

**Phase 2 — Local, automated**

- Same script, same embedding path, same Chroma store
- macOS/Linux `crontab` runs the script nightly at midnight
- Incremental sync means only edited pages are re-processed (and so only changed chunks are re-embedded — keeping inference token usage minimal)

**Phase 3 — Cloud, fully automated**

- Script deployed as an AWS Lambda function
- Triggered nightly by an AWS EventBridge scheduled rule
- Vectors stored in Pinecone (hosted); embedding via Pinecone integrated inference
- **No `torch` / no local model weights in the Lambda image** — embedding is a hosted API call, so the ingestion Lambda stays small and cold starts are a non-issue (a benefit of the hosted-embedding switch; matters less here than for the query Lambda since ingestion runs unattended, but it simplifies packaging)
- **No durable sync-state file needed** — the reconcile/incremental logic (see *Sync strategy*) reads `last_edited_time` and page IDs straight from chunk metadata in the vector store, so the stateless Lambda's ephemeral filesystem is a non-issue: the store is the source of truth for what's indexed and when
- Runs independently of local machine
- Timed to deploy alongside the query layer's production launch (the query layer runs on Lightsail, not Lambda; ingestion stays on Lambda + EventBridge — the two layers run on different AWS services)

---

## Decisions Log

### Source: Notion API vs manual export

**Decision:** Use the Notion API directly — no manual file exports.

**Rationale:** Manual exports (.md or .html zip files) require repeated human steps, make incremental updates painful, and introduce duplication risk. The Notion API provides structured access to page content and metadata including `last_edited_time`, enabling fully automated incremental sync.

**Setup:** Create a free internal Notion integration at notion.so/my-integrations. Any page shared with that integration is accessible to the script.

---

### Scope: What gets indexed

**Decision:** A dedicated `Portfolio` section in Notion acts as the inclusion boundary. Anything inside it is indexed; everything else is invisible to the script.

**Recursion depth (working choice — confirm):** "inside the Portfolio section" means the **full subtree** under the Portfolio parent page — direct child pages *and* any pages nested beneath them — not just the immediate children. Rationale: it matches the mental model "anything I put in the Portfolio section is indexed," and the opposite failure mode (silently *not* indexing a nested detail page you intended to publish, so the widget can't answer about it) is worse for a recruiter-facing tool than over-inclusion, which the **pre-ingestion audit** already backstops. The mark-and-sweep reconcile (see *Sync strategy* below) needs a definite "current in-scope set" to diff against, so this had to be pinned down. *(If you'd rather be more conservative about exposure, direct-children-only is the alternative — flip this and the enumeration walks one level instead of recursing.)*

> **Build-time content (synthetic seed, swapped at launch).** During the M1–M3 build the Portfolio subtree is populated with a **clearly-fictional persona** matched in shape to the real content (comparable page count and lengths), so ingestion and downstream calibration can run before real authoring exists. Real content is authored separately (`M1.1-01b`) and swapped in as a launch gate (`M4.2-03`); the mark-and-sweep reconcile (see *Sync strategy* below) makes the swap a content-only operation — synthetic chunks are deleted as out-of-scope, real chunks embedded, no code change. The **pre-ingestion audit applies to the real content**; synthetic content needs none. *(Recorded under "defer, don't drop" — see the cross-doc restructure note.)*

**Rationale:** Avoids the need to clean up the entire Notion workspace. Messy personal notes, unrelated projects, etc. remain private by default. You stay in control by simply moving or adding pages to the Portfolio section.

**Recommended content:** one page per work role, one page per project, skills/tech stack page, about me page, what I'm looking for page. *(During the build these pages hold synthetic placeholder content of the same shape; see the build-time note above.)*

---

### Sync strategy: incremental embed + mark-and-sweep reconcile

**Decision:** On each run:

1. **Enumerate** the page IDs currently in the Portfolio subtree (the "desired set").
2. **Reconcile deletions (mark-and-sweep):** read the page IDs already present in the vector store (from chunk metadata) and **delete the chunks of any page that is in the store but no longer in Portfolio** — i.e. pages that were moved out (de-curated) or deleted in Notion.
3. **Incremental embed:** for each page still in scope, compare its `last_edited_time` against the value stamped on that page's stored chunks; **only re-embed pages that have changed** (or are new).
4. **Delete-before-upsert per changed page:** when re-embedding a changed page, **delete all of that page's existing chunks first, then upsert the new ones** — never a bare upsert.

**Rationale:**

- **Incremental embed** keeps re-runs cheap and fast (only changed pages are re-embedded), which is why nightly or more-frequent runs are practical and inference-token use stays minimal.
- **Mark-and-sweep closes the removal hole.** The original design keyed only on `last_edited_time` of pages *currently in* Portfolio, so it handled additions and edits but **not removals** — a page moved out of Portfolio or deleted in Notion left its chunks in the store, still retrievable. That punctures the system-wide safety boundary ("nothing outside Portfolio can surface"). The sweep makes curation control *removal* as well as *addition*, at the cost of one enumeration + a set-diff per run and **no extra inference**.
- **Delete-before-upsert fixes orphaned chunks.** When an edited page re-chunks to *fewer* pieces, a bare upsert-by-ID overwrites the surviving chunk positions but leaves the old tail chunks (higher position index) as orphans. Deleting the page's chunks first clears them — and reuses the same `delete` primitive the sweep already needs.
- **The store is its own sync state.** Because the run reads each stored page's `last_edited_time` from chunk metadata anyway, there is **no separate "last successful sync" timestamp file to keep** — the vector store *is* the source of truth for what's indexed and when. This matters at Phase 3: a stateless Lambda has no durable local filesystem to hold a global timestamp, and this design needs none.

> **Update — supersedes the original framing.** The first version of this decision read: *"compare each page's `last_edited_time` against the timestamp of the last successful sync; only re-embed pages that have changed."* That covered edits and additions but silently assumed an append/edit-only world (no deletions, no shrinking pages, and a durable global timestamp). The mechanism above is a strict superset — same incremental-embed core, plus reconciliation — and is kept for correctness and for the system-wide safety boundary. Original reasoning retained here for history.

---

### Chunk metadata: store a public source URL/slug (for Layer 2 citations)

**Decision:** Each chunk's metadata carries a public **`url`** (or a **slug** the widget can build one from), and an optional **`anchor`** reserved for future deep-linking. This is in addition to page ID, title, last edited time, and chunk position.

**Why:** the Layer 2 query pipeline returns sources to the React widget and links each one to a real page on the portfolio site ("read more →"). The widget can only build that link if the chunk knows its public destination, so the URL/slug must be stamped on at ingestion time.

**Phasing (decoupled, so ingestion isn't blocked on a content site):**

- Add the field now; leave `url` **null** until the public portfolio pages exist. Layer 2 ships inline source snippets immediately and the links simply activate once URLs are populated.
- **Page-level URL first.** `anchor` (jump-to-passage) is a later refinement — ~500-token chunks don't align to headings, so a clean anchor often doesn't exist; revisit only if pages are templated with stable section IDs.

**Cross-layer note:** depends on a separate task outside ingestion — building the public portfolio pages and deciding the slug scheme. Until those exist, the field is carried but empty.

---

### Chunking: ~500-token windows + word-based token approximation

**Decision:** Split page text into **~500-token windows with ~50-token overlap**, carrying a `chunk_position` ordinal. The token budget is approximated by **whitespace word count** (~0.75 words/token), *not* the embedding model's exact tokeniser. *(Req: `M1.4-01` · L1 Chunk.)*

**Rationale:**
- `llama-text-embed-v2` is **hosted** (no local `torch`/`transformers`), so its exact tokeniser isn't available in-process — and pulling a model tokeniser in would reintroduce the heavy dependency the hosted-embedding switch deliberately removed.
- Exact token counting is **not load-bearing here**: the model's **2048-token input cap is ~4× the ~500-token target**, so a generous word-based approximation stays comfortably within range. The failure mode that mattered — exceeding the cap and silently truncating — cannot happen with this much headroom.
- ~500 tokens balances retrieval precision (smaller → more precise passages) against answer coherence; ~50-token overlap stops an answer being split across a boundary.

**Rejected / deferred alternative:** add **`tiktoken`** for a closer token count. It's lightweight (no `torch`), but it's still only an *approximation* of the Llama tokeniser and adds a dependency to the locked baseline for no practical gain at this scale. Revisit only if real content (`M1.1-01b`) introduces pages long enough to approach the 2048 cap, or if the embedding-model lock changes.

**Implementation:** `ingest/chunker.py` — `chunk_text` / `chunk_page` / `chunk_pages` and the `Chunk` record. Word window = `round(chunk_tokens * 0.75)`, overlap = `round(overlap_tokens * 0.75)`.

---

### Chunk metadata: nullable source `url` / `anchor`

**Decision:** Every chunk carries a public **`url`** (slug) and an optional **`anchor`** in its metadata. Both are **nullable** and empty for now — populated later when the public portfolio pages exist (C2 / `M4.5-01`). *(Req: `M1.7-01` · L1 Chunk metadata.)*

**Representation (verified):** Chroma **silently drops a metadata key whose value is `None`** — `get` returns the record *without* that key — which would violate "chunks carry the `url`/`anchor` keys" and break Layer 2's straight-through `sources` passthrough. So null is stored as the **empty string `""`** (which Chroma preserves — also verified); the domain `Chunk` uses `str | None`, and Layer 2 reads `""` back as `null`.

**Why stamp now:** Layer 2's fixed `sources` event reserves `url` (nullable) and `anchor` (nullable). Carrying the keys from ingestion means the widget's "read more →" links activate later with **zero widget or schema change** — only the values get filled in (C2).

---

### Embedding model: hosted Pinecone Inference (revised)

**Decision:** Embed chunks via a **hosted model on Pinecone Inference** — working choice `llama-text-embed-v2` at **384 dimensions**, with `input_type=passage`. This **supersedes** the original choice of `all-MiniLM-L6-v2` run locally via `sentence-transformers`.

**Why it changed:** the Layer 2 query pipeline must embed incoming questions with the *same* model as the chunks. Running `all-MiniLM-L6-v2` locally would have meant `torch` inside the query Lambda — a ~1.2 GB stack with 20–30s cold starts on a public, synchronous endpoint (enough to hit API Gateway's 29s timeout), with the only clean fix (provisioned concurrency) costing money continuously. A hosted endpoint removes `torch` entirely and reduces query embedding to a fast API call. Since the same model must be used on both sides, ingestion moves to the hosted model too. (Pinecone does not host `all-MiniLM-L6-v2`, so keeping L6 *and* going hosted was not possible — confirm the live catalogue with `pc.inference.list_models()`.)

> **Update — reasoning superseded, decision unchanged.** The Lambda cold-start argument above no longer applies: the query service was later moved off Lambda to an **always-warm AWS Lightsail VPS**, where a local model would load once at startup with no per-request cold start. **Hosted embedding still wins, now on cost:** `torch` + the model needs ~2 GB RAM (≈$12/mo Lightsail tier), while hosted embedding keeps both the query app *and* the ingestion Lambda free of `torch`, fitting the smallest tiers — saving ~$7/mo on the query VPS and keeping the ingestion Lambda small. The original reasoning is kept above for history; the decision is unchanged.

**Rationale for the hosted choice:**

- `llama-text-embed-v2` supports variable output dimensions including **384**, and benchmarks above OpenAI's large embedding model
- Pinecone Starter free tier includes ~5M inference tokens/month — far beyond what a curated portfolio corpus needs, even with periodic re-embeds
- One vendor for embedding *and* vector storage in production ("one-stop shop"), and integrated inference can embed + upsert in a single call
- Local dev still uses Chroma — embedding source is decoupled from the vector store

**What we give up vs the original:** the "fully local, fully free, offline, no account, Apache-2.0" property of L6-v2. Embedding now depends on the Pinecone API and an API key.

**Asymmetric encoding (action item):** chunks must be embedded as **`passage`** here, and queries as **`query`** in Layer 2. (The e5 family enforces this via `query:`/`passage:` markers; `llama-text-embed-v2` is not e5, but Pinecone's API exposes `input_type` for hosted models regardless — set it correctly on both sides.)

**Important:** all chunks must be embedded with the same model as the queries. Since the model switch happened during design — before any vectors were created — this simply means embedding with the hosted model from the start; there is **no prior L6-v2 corpus to migrate**. (Switching models *after* go-live would require re-embedding everything.)

**Final model lock is a minor open sub-decision:** `llama-text-embed-v2` @ 384 (working choice) vs `multilingual-e5-large` @ 1024. The *strategy* (hosted, not local) is settled.

> **LOCKED — M0.5-01 (verified against the live API, 2026-06-18).** Lock = **`llama-text-embed-v2` @ 384-dim, cosine, `input_type=passage`** (queries `query` in L2). `pc.inference.list_models()` confirmed the model is hosted (catalogue: `llama-text-embed-v2`, `multilingual-e5-large`, `pinecone-sparse-english-v0`, plus rerankers); a `dimension=384` passage embed returned a 384-length vector — the 1024 default trap avoided. Recorded in `config.py` (`EMBED_MODEL`/`EMBED_DIM`/`EMBED_METRIC`). `multilingual-e5-large` @ 1024 set aside. The "working choice" wording above is retained for history.

---

### Vector store: Chroma (dev) + Pinecone (prod)

**Decision:** Use Chroma locally during development; switch to Pinecone for production. (Unchanged by the embedding switch.)

**Rationale:**

- Chroma requires zero configuration — `pip install chromadb`, data saved to a local folder. Ideal for building and testing.
- Pinecone is hosted — the production Lambda can reach it from anywhere, unlike a local Chroma store. Free tier is comfortably sufficient for a personal project. *(Verified: Starter gives 2 GB storage, 5 indexes, 2M write / 1M read units per month, plus ~5M embedding inference tokens/month — far beyond a few-hundred-chunk corpus. Starter indexes are AWS `us-east-1` only, which is fine here.)* It now also provides the embedding model, consolidating the production stack.
- The switch between the two is a small code change since both expose similar Python APIs.
- **Index dimension must match the embedding model** (384 for `llama-text-embed-v2` @ 384). Configure the index for **cosine** similarity to match Layer 2. **Implementation gotcha (verified):** `llama-text-embed-v2` defaults to **1024** dimensions — getting 384 requires explicitly passing the `dimension` parameter on the embed call *and* creating the Pinecone index at 384. A mismatch here produces a working-but-wrong system (silent 1024-dim vectors, or an upsert dimension error), so check the returned vector length once at setup.

**Rejected alternative:** AWS OpenSearch / pgvector on RDS — both viable but over-engineered and costly for a personal portfolio site.

---

### Cron / scheduling: laptop cron → EventBridge

**Decision:** Phase 2 uses macOS `crontab`; Phase 3 migrates to AWS EventBridge when the query API is deployed.

**Rationale:** No point running cloud infrastructure for ingestion while the vector store is still local. EventBridge is a trivial addition at deploy time and costs nothing at this scale.

---

## Libraries & Dependencies

| Package | Purpose |
| --- | --- |
| `notion-client` | Official Notion API Python SDK |
| `pinecone` | Hosted embedding (Inference API) + vector store (production) |
| `chromadb` | Local vector store (dev) |

> Removed vs the original design: `sentence-transformers` (no longer needed — embedding is a hosted API call, not a local model run). The legacy `pinecone-client` package is superseded by `pinecone`.

---

## Open Questions / Next Steps

- [ ]  Write the ingestion script (`ingest.py`) — including the **mark-and-sweep reconcile** (enumerate Portfolio subtree → delete chunks of pages no longer in scope → delete-before-upsert per changed page)
- [ ]  Set up Notion internal integration and share Portfolio pages
- [ ]  Set up Pinecone account, API key, and an index sized to the chosen model's dimension (cosine) — verify the returned vector length is 384, not the 1024 default
- [ ]  Lock the final hosted embedding model + dimension (shared with Layer 2). Input length is **confirmed** for the working choice (`llama-text-embed-v2`, 2048-token limit ≫ ~500-token chunks); re-confirm only if the lock changes the model (e.g. to `multilingual-e5-large`)
- [ ]  Confirm the Portfolio scope recursion depth (working choice: full subtree). Author the **synthetic seed corpus** (`M1.1-01a`) to unblock the build; **real authoring + pre-ingestion audit deferred to `M1.1-01b`**, consumed at the `M4.2-03` swap
- [ ]  Define **reusable** Portfolio page templates (work role / project / skills / about / looking-for) — used for both the synthetic seed and the real content (`M1.1-01a`)
- [ ]  Test chunking against the shape-matched **synthetic seed** first; re-confirm on **real content at the `M4.2-03` swap**
