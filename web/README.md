# RAG Widget (Layer 3)

The `'use client'` "ask me anything" chat widget — a first-party Next.js (App Router) component
that consumes the Layer-2 `POST /v1/ask` SSE endpoint. Part of the RAG portfolio **monorepo**
(the Python backend lives in the repo root). Built across the M3 tickets.

## Run

```bash
npm install
npm run dev        # http://localhost:3000  (needs the backend running — see below)
```

The widget calls the API at `NEXT_PUBLIC_API_BASE_URL` (`.env.local`, default `http://localhost:8000`).
Start the backend too, from the repo root:

```bash
uvicorn query.api:app --reload --port 8000
```

## Checks (run these for any M3+ slice — separate from the Python `ruff`/`mypy`/`pytest`)

```bash
npm run test        # vitest
npm run typecheck   # tsc --noEmit
npm run build       # next build
```

## Structure

- `app/` — App Router: `layout.tsx`, `page.tsx` (mounts the widget inline).
- `components/AskWidget.tsx` — the `'use client'` widget (M3.1 scaffold; M3.2 `useReducer`).
- `components/SourceCards.tsx` — source cards: group-by-title + provenance label (M3.3).
- `lib/sse.ts` — hand-rolled fetch + SSE parser, 4 obligations (M3.1-02).
- `lib/reducer.ts` — typed state machine `idle → submitting → streaming → done | error` (M3.2-01).
- `lib/sources.ts` — display-only group-by-title (M3.3).
- `lib/types.ts` — shared `Source` / `Exchange` types.

## Design source of truth

`../docs/L3_Presentation.md` (Decisions 1–11). Ticket status is live in Notion (`DB Action Items`).

## Still to do (M3)

`M3.4` chips + input defaults · `M3.5` error/abort/retry · `M3.6` accessibility (the live screen-reader
test `M3.6-02` is **manual**, Nic) · `M3.7` CSS-Modules styling. The current inline styles are
placeholders until M3.7.
