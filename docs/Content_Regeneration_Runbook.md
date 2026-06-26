# Content Regeneration Runbook — synthetic → real (M4.2-03)

How to swap the placeholder **"Marlowe Finch"** persona for Nic's real content and re-launch. This
is ticket **M4.2-03**, the launch gate. Run it end-to-end once the real content is authored.

> The system is deliberately built so this is a **content + calibration** swap, not a code rewrite —
> every layer reads from Notion/config, not hardcoded facts. The only "code" edits (`eval_set.py`,
> `chips.ts`) are content by nature.

## Prerequisite
- Real portfolio content authored in Notion under the Portfolio parent (`PORTFOLIO_PARENT_PAGE_ID`),
  **replacing** the synthetic Marlowe pages (ticket **M1.1-01b**). Audit: no fictional
  names/companies/projects/metrics remain.

## Steps

### 1 — Point the corpus at real content (Notion)
Replace the synthetic pages under the Portfolio parent with the real ones. Ingestion enumerates that
subtree, so there's no config change — just the Notion content.

### 2 — Rewrite the eval set (`query/eval_set.py`)
The ~15 should-answer / ~15 should-refuse questions are both the **calibration measuring stick** and
the **source for the widget chips**. Rewrite them for the real content:
- *should-answer*: questions the real content genuinely covers (real roles, projects, skills…).
- *should-refuse*: off-topic / unanswerable / injection (mostly reusable as-is).

### 3 — Re-ingest locally + re-calibrate the threshold (Chroma)
```bash
python -m ingest.embed_store        # rebuild local Chroma from the real Notion content
python -m query.calibrate           # prints should-answer/refuse distributions + recommended threshold
```
Set `config.RELEVANCE_THRESHOLD` to the recommended value (bottom of the should-answer gap). Confirm
a **clean gap** (`clean gap? : True`, `refuse leaking: 0`). Calibration runs against the default
Chroma store; the value travels unchanged to Pinecone (parity verified at M4.2-01). If the gap is
**not** clean, retrieval/chunking needs attention before continuing — don't just lower the threshold.

### 4 — Regenerate the suggested-question chips (`web/lib/chips.ts`)
Pick 3–4 strong should-answer questions, **live-validate** each against the local API
(`uvicorn query.api:app` + `web` dev server) so none demo a decline, then update `web/lib/chips.ts`.
(Same procedure as M3.4.)

### 5 — Re-ingest into PROD Pinecone (clear + re-stamp)
`ingest/sync.py` (mark-and-sweep) is **local/Chroma only** — by design (see the M4.2-02 deferral in
`L1_Ingestion.md`). For the wholesale synthetic→real swap, clear the prod index and re-stamp:
```bash
python -c "from ingest.embed_store import get_index; get_index().delete(delete_all=True)"
VECTOR_STORE=pinecone python -m ingest.embed_store
```
Clearing drops the stale synthetic vectors; the re-stamp upserts the real ones (text in metadata).

### 6 — Ship the updated backend + widget
- **Backend (Lightsail):** the new `RELEVANCE_THRESHOLD` is in `config.py` — on the box,
  `git pull` then `sudo systemctl restart rag-api`.
- **Widget (site repo):** copy the updated `web/lib/chips.ts` into `nicjranum.uk`, open a PR → merge
  → Azure redeploys. (This is the "if the swap changes the chips, re-run M4.3-01" note in the backlog.)

### 7 — Verify (re-run M4.4-01 on real content)
- Real should-answer questions at `https://nicjranum.uk/ask` → grounded answers + source cards.
- Off-topic → declines; streaming is incremental through Cloudflare; no CORS errors.
- **Name check:** answers now read "Nic" consistently — the synthetic "Marlowe"/"Nic" mix disappears
  because the corpus name finally matches the system prompt (`query/prompt.py`, already "Nic").

## Already in place vs. manual for this swap
- ✅ **In place:** pluggable store (M4.2-01), embed→store→retrieve pipeline, the calibration tool,
  the system prompt (already "Nic"), and the backend + widget ship paths.
- ✍️ **Manual (content by nature):** rewrite `eval_set.py` + `chips.ts`.
- ⚠️ **One gap to know:** there is **no incremental mark-and-sweep against Pinecone** — the swap is a
  deliberate **clear + re-stamp** (step 5). Fine for a one-time wholesale swap; nightly automation
  was deliberately not built (M4.2-02 deferred).
