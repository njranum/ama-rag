## Overview

This page documents the architecture for the **Presentation / Frontend Layer** (Layer 3) of the RAG personal portfolio project, along with the reasoning behind each key decision.

Layer 3 is the only layer the visitor actually touches: the **"ask me anything" chat widget** embedded on Nic's personal site. It captures a question, calls the Layer 2 `POST /v1/ask` endpoint, consumes the SSE stream, renders the answer token-by-token, shows the source snippets, and handles every UX state (loading, streaming, done, error, the bare decline). It runs **per request, in the visitor's browser** — the client half of the contract whose server half is fully specified in Layer 2.

> **Status:** all design decisions are settled — distribution model, form factor, SSE consumption, state model, source display, interaction UX, error handling, accessibility, styling, and config/deployment. What remains is implementation, tracked under *Open Questions / Next Steps*.

> **Scope boundary (decided up front):**
> - **C2 (public portfolio content pages) is *not* in this layer.** The widget functions fully without it — inline snippets render from the `text` field immediately, and the contract carries `url` as nullable so links activate later with *zero* widget change. C2 is a content-authoring + site-architecture task plus a Layer 1 change (populate `url` at ingestion); none of it is widget work. Tracked as its own future task/layer.
> - **Operational concerns (observability, cost monitoring, answer-quality evaluation) belong to a future Layer 4.** They are server-side or cross-cutting, and the eval piece overlaps Layer 2's Phase-1 threshold calibration. The one genuinely-frontend sliver (client error capture / usage analytics) was considered here and deliberately deferred — see Decision 11.

---

## Architecture: How It Works

The widget is a **first-party React (client) component** living in the existing Next.js codebase. Its runtime flow:

```
Visitor types a question (or taps a suggested-question chip)
    ↓  (Enter-to-send; client-side 500-char cap mirrors server)
fetch() POST /v1/ask   ← hand-rolled; NOT native EventSource (POST has a body; EventSource is GET-only)
    ↓
Check response.status BEFORE reading the body
    ├─ 429 → rate-limited error state (pre-stream branch, no parse loop)
    └─ ok → read response.body as a stream
              ↓  (manual SSE parse: buffer across chunks, associate event:+data:)
        ┌───────────────────────────────────────────────┐
        │  event: sources  → render source cards now      │  ← exits loading state
        │  event: delta    → append token (pre-wrap)      │  ← streaming
        │  event: done     → finalise; announce to SR     │
        │  event: error    → keep partial text + note     │
        └───────────────────────────────────────────────┘
    ↓
Typed reducer (idle → submitting → streaming → done | error{kind})
    ↓
Render into the inline panel: discrete Q→A→Sources pairs, in a bounded scrolling transcript
```

The visible answer streams for sighted users; a separate hidden `aria-live="polite"` region announces the completed answer to screen readers. Source cards populate the instant the `sources` event lands — even while the answer is still streaming — so the visitor reads "here's what I found, now composing."

---

## Deployment Phases

Layer 3 has **no Phase-1 equivalent** — Layer 2's Phase 1 is a plain CLI with no UI. The widget therefore runs in two phases that ride on Layer 2's Phase 2 and Phase 3.

**Phase 2 — Local (widget against local API)**

- Widget runs on the Next.js dev server; points at the local FastAPI endpoint (`localhost`) via `.env.local`
- Exercises the real request/response contract and streaming behaviour end-to-end against local Chroma
- Purpose: prove SSE consumption, the reducer state transitions, and rendering before any cloud infra
- **Requires the Layer 2 CORS allowlist to include the dev origin** (`http://localhost:3000`) — see the cross-layer note under Decision 10

**Phase 3 — Cloud (production)**

- Widget ships through the **existing GitHub Action → Azure pipeline** (it's a component in the Next.js repo — no separate bundle, no separate hosting, no cache-busting)
- Points at the Cloudflare-fronted Lightsail production origin, set in the Action's build environment
- Source "read more →" links remain inert (`url` null) until C2 exists; inline snippets work from day one
- Verify streaming survives the round trip — in particular that **Cloudflare passes `text/event-stream` through without buffering** (already on Layer 2's Phase-3 checklist)

---

## Decisions Log

### Decision 1 — Distribution / embedding model

**Decision:** Ship the widget as a **first-party React component** inside the existing Next.js codebase, sharing the site's React runtime and deploying through the existing pipeline.

**Rationale:** The site is React (Next.js), so a React runtime is already present on every page. A first-party component is the simplest possible path: no second copy of React, no style-injection plumbing, no frame boundary. It deploys through the GitHub Action already in place.

**Rejected alternatives:**

- **Self-mounting embed bundle** (`<script>` + mount point, React bundled in, shadow-DOM isolated — the Intercom/Crisp model). Exists for hosts you *don't* control or that aren't React. On a React site you own, it's pure overhead — bundling a second React to sit inside the first.
- **iframe.** Total isolation, but clunky: awkward height/resize handling, focus and mobile-keyboard quirks, and theming has to cross the frame boundary. Only worth it behind a hard security/style wall, which an owned site doesn't need.

**Site rewrite kept firmly out of scope.** Nic noted the site is "poorly built" and is open to rearchitecting. A first-party component is decoupled from the rest of the site's quality — it mounts in one place, calls an external API, renders itself, and doesn't care whether the surrounding site is clean or messy, App Router or Pages Router. Adding the widget therefore does **not** require (and must not trigger) a site rewrite; coupling the two would blow this layer's scope open and stall a portfolio piece on a yak-shave. A rewrite is a legitimate but *separate* effort.

**Consequence (not a choice, a constraint):** the widget is necessarily a **client component** (`'use client'`) — all streaming happens in the browser. This rules out doing any of it in a server component and is load-bearing for Decision 3.

**Deferred — note, not built:** the *one* future scenario where the embed bundle would matter is wanting the same widget on a second, non-React site. Speculative at portfolio scale. A clean first-party component can be repackaged into an embed bundle later if that day comes.

---

### Decision 2 — Form factor

**Decision:** An **inline embedded panel** (lives in the page's layout flow), not a floating launcher bubble or a full-page route.

**Rationale:** For a portfolio piece, an inline panel reads as "a thing I deliberately built and embedded here," which is the impression a recruiter should form. A floating support-bubble reads as "generic chatbot bolted on"; a full-page route requires navigation and is less likely to be discovered by a skimming visitor. The inline panel also avoids z-index/overlay headaches.

**Rejected alternatives:** floating launcher bubble (support-chat connotation; covers content on mobile); full-page `/ask` route (requires navigation; lower discovery).

**Consequences banked (resolved in later decisions):**

- The **empty/initial state matters more** than it would behind a launcher — the panel is visible immediately, so the placeholder + suggested questions *are* the first impression (drives Decision 6's suggested-question chips).
- **Transcript-vs-height tension** — a growing transcript inside an in-flow panel must scroll *inside* a bounded container or it shoves the page down (resolved in Decision 6: bounded internally-scrolling transcript).
- **Higher style-bleed exposure** — sitting in the page flow surrounded by site content, the panel is *more* exposed to stray global CSS than an isolated bubble would be (resolved in Decision 9: CSS Modules + root reset).

---

### Decision 3 — SSE consumption mechanism

**Decision:** Consume the stream with a **hand-rolled `fetch()` + manual SSE parser** — no library.

**The constraint that eliminates the obvious option:** the browser's native `EventSource` only makes **GET** requests and can't send a body or custom headers. The Layer 2 contract is deliberately `POST` with the question in the body (the privacy choice — keep free-text input out of URLs, server logs, browser history, and `Referer` headers). So `EventSource` is out, and consumption routes through `fetch()`, whose `response.body` is a readable stream that works with any HTTP method.

**Why hand-rolled (Nic's call):** Nic wants to see the insides of the mechanism — a legitimate driver, and SSE-over-fetch is well-trodden (the manual parser is ~20–30 lines and a recognised approach, not a hack). In every viable option the `fetch` call is owned anyway (for POST, the 429-before-stream check, `AbortController`, and CORS), so the only thing actually delegated by a library would be the parsing — which Nic chose to keep.

**Rejected alternatives:**

- **Thin SSE parser library** (`fetch-event-stream` / `eventsource-parser`) — the recommended *lean* (delegates only the fiddly byte-buffering while keeping fetch/429/abort explicit). Not chosen: Nic wants the mechanism visible. Fully interchangeable later if the hand-rolled parser proves annoying.
- **All-in-one (Vercel AI SDK / `@microsoft/fetch-event-source`).** Rejected deliberately: the AI SDK is the reflexive 2026 default but is built around *its own* streaming protocol and `useChat` hook. Adopting it would mean either bending the deliberately-custom typed-event contract to match the SDK (a rewrite rippling back into Layer 2 for no benefit) or wrapping the endpoint to fake its protocol. Powerful tool, wrong problem.

**Implementation obligations (the price of hand-rolling — recorded, not pre-solved):**

1. **Cross-chunk line buffering.** A `data:`/`event:` line can split across two `read()` calls. Buffer, split on the `\n\n` event delimiter, carry the trailing incomplete segment into the next read. *This* is the classic bug — get it wrong and tokens drop intermittently.
2. **Named-event association.** The contract uses `event: sources|delta|done|error` each paired with `data:` — not `data:`-only. Read both lines per event block and associate them, resetting between blocks. Most online examples only handle `data:`.
3. **Streaming UTF-8 decode.** Use `TextDecoder` with `decode(chunk, {stream: true})`, or a multi-byte character split across a chunk boundary becomes mojibake.
4. **Skip comment lines.** A line starting with `:` is an SSE comment — ignore it. This is exactly the `: ping` keepalive in the watch-item below, so building it in now means a future keepalive costs zero widget change.

**Watch-item (potential Layer 2 ripple — not actioned):** if embedding + retrieval + first-token latency ever leaves the connection idle long enough for Cloudflare to drop it, the fix is a `: ping` comment heartbeat emitted by Layer 2. The stream sends `sources` almost immediately, so idle time should be minimal; revisit only if end-to-end testing through Cloudflare shows drops.

---

### Decision 4 — State model & token rendering

**Decisions:**

- **A typed status union driven by `useReducer`.** One `status` field (`idle → submitting → streaming → done`, plus a terminal `error`) with `answer`, `sources`, and `error` on the state object, and events `SUBMIT / SOURCES / DELTA / DONE / ERROR / RESET`. Avoids **boolean soup** (`isLoading`/`isStreaming`/`isError` flags) which permits impossible states (loading-and-errored) and turns bug-prone. The reducer also becomes the single tap point for future ops instrumentation (see Decision 11).
- **The decline is *not* a distinct state.** Per the contract, the bare decline arrives as a normal `delta`+`done` — so at the data layer a decline is simply *an answer*, rendered through the same path as any other. We explicitly do **not** detect or style it specially: the only way to "detect" it would be string-matching Layer 2's canned wording, which Layer 2 reserved the right to soften — coupling the widget to exact text is fragile. *Note there are two decline shapes: the **gate** decline carries no `sources` event (renders as an answer with no sources); the **prompt-side** decline arrives **with** a `sources` event already on screen. Both are still "just an answer" at the state layer — the state model needs no special case. The only thing the prompt-side decline required was an honest sources **label** so the cards don't read as a false claim of support; that is a rendering concern, settled in Decision 5, not a new state.*
- **The 429 is a genuinely separate, pre-stream branch.** It's an HTTP `429` with a JSON body arriving *before* the stream opens, caught in the fetch wrapper by checking `response.status` before entering the parse loop — never an SSE event. Modelled as one `error` state carrying a discriminated **`kind`** (`rate_limited | stream | network`), so the machine stays simple while the message can be specific.
- **Plain text + `white-space: pre-wrap`**, not a markdown renderer.

**Rationale (rendering):** the system prompt already steers Haiku to plain prose. Plain text + pre-wrap (1) sidesteps rendering *partial* markdown mid-stream, where a half-written `**` renders as garbage then snaps into place on the closing token (flicker + reflow every token); (2) carries no HTML-sanitisation/XSS surface; (3) needs no dependency. Worst case Haiku emits literal asterisks — minor, fixable by tightening the prompt's no-markdown instruction (a trivial Layer 2 ripple) rather than by adopting a streaming markdown renderer. Pairs cleanly with Decision 5: links live in the *sources* UI, not the answer text.

**Deferred:** XState (a formal state-machine library) — nice for complex flows, premature for ~5 states with one happy path. The streaming **markdown renderer** — note and defer.

---

### Decision 5 — Source display

**Decisions:**

- **Render sources on arrival.** The `sources` event arrives first (by Layer 2 design, *for* the widget). Render the cards the instant it lands — this doubles as the exit from the loading state and productively fills the latency gap before the first token. The visitor sees "found these → now composing."
- **Group source cards by page title (display-only).** With k=4 and ~50-token chunk overlap, multiple retrieved chunks often come from the same Notion page; rendered flat that's repeated identical titles, which reads as broken. A one-line `groupBy` collapses them (array is already best-match-first, so the lead chunk represents the group).
  - *Distinct from a deferred Layer 2 item:* Layer 2 deferred *adjacent-chunk deduplication at retrieval* (not wasting a top-k slot / not diluting the **prompt**). This is purely **display** grouping (how many cards the human sees). Independent and cheap, so done now.
- **Compact preview + ellipsis.** The `text` field is a full ~500-token chunk that starts and ends mid-sentence. Render a short line-clamped preview wrapped in leading + trailing ellipsis to signal "excerpt." Respects the inline panel's bounded height.
- **"read more →" link renders only when `url` is non-null.** Title + preview always show; the link appears conditionally. When C2 ships and ingestion populates `url`, links light up with zero widget change — exactly what the nullable-`url` contract was designed for.
- **Null-`url` note — suppress when *all* sources are null, show only in the mixed state.** At launch (pre-C2) every `url` is null, so a per-card note would appear on every card of every answer and read as half-broken. Suppress it entirely when the whole set is null (clean launch state); show a muted, inert **"No linked page yet."** only when *some* cards link and some don't, where it's genuinely informative. (Framing note: the excerpt *is* the source — only the fuller page is pending — so "no linked page" is accurate where "source unavailable" would not be.)
- **Gate decline → no sources block at all.** When the *retrieval gate* fires (Layer 2 sends no `sources` event), render nothing for sources — crucially, no empty header over a decline.
- **Prompt-side decline → sources are already on screen; the label must stay honest.** There is a *second* decline path: the context cleared the retrieval gate but Haiku judged it insufficient and declined. By then the `sources` event has *already streamed* (it is emitted before the LLM is even called, to fill the latency gap), so the widget cannot retract it, and cannot detect the decline without string-matching wording Layer 2 reserved the right to change. The fix is to make the sources label honest on *every* path rather than to detect the decline — see the label decision below.
- **Label: a provenance label, not a causation label.** Working choice: **"From Nic's portfolio:"** (alternatives: "Closest matches:", plain "Sources:"). Final wording lockable at build time.

> **Update — supersedes the original "Based on:" choice.** The original decision was *"Label: 'Based on:' rather than 'Sources:'/'Citations:' — warmer, fits the approachable-professional tone, still does the trust job."* The warmth call still stands, but "Based **on**:" asserts that the answer was *derived from* the chunks — a claim that is false on the prompt-side decline path (sources shown above "Sorry, I don't have information about that" reads as a contradiction) and arguably overclaims even on a normal answer, since the model may not lean on all four chunks. A **provenance-asserting** label ("these are what was retrieved from Nic's portfolio") is true on every path: above an answer it reads naturally, and above a decline it reads coherently as *"I searched Nic's portfolio, here's the closest material, and it doesn't cover your question."* This needs **no decline detection and no contract change** — the cheapest possible fix. The trade-off is a sliver of warmth versus the original "Based on:"; "From Nic's portfolio:" recovers most of it. *(The original rejected-"Sources:" reasoning is partly rehabilitated by this: the objection to "Sources:" was tone, not honesty.)*
>
> **Deferred escalation (recorded, not built):** a **structured, machine-readable decline signal** on the Layer 2 contract (so the server knows whether to suppress sources) is the heavier "proper" fix. Deferred because it costs a contract change, prompt complexity, and a latency hit (the server would have to know the answer is a decline *before* streaming sources). Revisit **only if** Layer 2's Phase-1 calibration shows the sources-then-decline case is frequent (see `L2_Query_Pipeline.md`). The honest label makes the rare case acceptable regardless, so this may stay deferred indefinitely.

**Deferred:** click-to-expand the full chunk text — a nice refinement, premature; the preview establishes provenance.

---

### Decision 6 — Interaction & conversation UX

**Decisions:**

- **Discrete-pairs transcript** (not ephemeral single-answer). The widget accumulates this session's Q&A pairs in client state, in a bounded internally-scrolling container. Each backend call stays independent and stateless — the transcript is never sent back, so single-turn is preserved. Framed as **discrete pairs** (each answer visually bound to its own question), *not* a flowing chat thread, to avoid the false-continuity trap: a chat-thread UI invites follow-ups ("and at his last job?") that assume memory the stateless backend can't provide, producing a confused decline that looks broken. The discrete-pairs framing signals "independent questions."
- **Suggested-question chips** in the empty state — 3–4 clickable chips that populate-and-send. They cure the blank-input problem (acute for an always-visible inline panel), make a strong first impression, and quietly steer visitors toward answerable topics, *reducing declines*. Sourced from Layer 2's Phase-1 **"should-answer" eval set** (questions already verified to be covered by the content).
- **Input defaults:** Enter-to-send; client-side 500-char cap mirroring the server cap, with a subtle counter near the limit (immediate feedback instead of eating a `400`); send disabled on empty/whitespace; send disabled while a request is in flight (ties to Decision 4 — submit allowed only from `idle`/`done`, preventing overlapping streams).

**Rejected alternative:** pure ephemeral (each answer replaces the last). Simplest and fully defensible — keeps the panel compact, doesn't imply memory — but a thinner artifact than a portfolio "chat widget" warrants.

**Deferred:** *true* multi-turn (conversation memory) — would be a Layer 2 contract change (session/history), explicitly out of scope.

> **Implemented (`M3.4-01`).** Chips + input defaults built in `web/components/AskWidget.tsx`; the chip set lives in `web/lib/chips.ts`. Because the Phase-1 should-answer set is a Python module (`query/eval_set.py`) that can't cross the layer boundary into the TS widget, the chips are a **hand-picked, provenance-tagged copy**, not a runtime import. Selection method: every should-answer candidate was **exercised live against the local FastAPI + Chroma stack** and kept only if it returned a *strong* grounded answer. Two covered-but-weak candidates were **dropped** — *"Where does Marlowe currently work?"* (retrieval missed the Orrery chunk → hedged) and *"What open source work has Marlowe done?"* (cleared the gate but answered with a hedge) — confirming the ticket's own warning that "chips must come from genuinely-covered questions or they'll demo a decline." Kept four spanning project / skills / hiring-fit / origin-story. **PROVISIONAL** (synthetic corpus) — re-pick and re-validate from the regenerated should-answer set at `M4.2-03`.
>
> **Flagged (Layer 2, not actioned here):** during this live validation, answers intermittently named **"Nic"** instead of the synthetic persona **"Marlowe"** — the system prompt (`query/prompt.py`) hardcodes "Nic" while the seed corpus uses "Marlowe Finch", so the model mixes the two. Self-resolves at the `M4.2-03` content swap (corpus name becomes "Nic"), but worth a consistency pass if synthetic demos are shown before then.

---

### Decision 7 — Error & resilience (client side)

Built on Decision 4's shape (one `error` state, discriminated `kind`, 429 caught pre-stream). Decision 7 is the policy and copy.

**Decisions:**

- **Time-to-first-event timeout only.** Layer 2 already has a server-side request timeout + fallback, so the client timeout is a backstop for "server never answers / hung connection." If the `sources` event (the first thing sent) hasn't arrived within ~10–15s, abort and show a `network` error. Once events are flowing, **trust the stream and never time out on duration** — deltas arriving *is* the health signal. This catches a dead server without ever guillotining a healthy long answer. Implemented via the `AbortController` already wired.
- **Keep the partial answer on a mid-stream `error`.** If deltas have rendered and then the `error` event arrives, keep the shown text and append a muted inline note ("— the response was interrupted"). The tokens shown are real, grounded output; discarding text the visitor was already reading feels more broken than the interruption.
- **Manual-only retry.** A "Try again" affordance on any terminal error; never auto-retry (auto-retrying a `429` is counterproductive; on a struggling server it piles on). For `rate_limited`, the copy implies waiting.
- **Abort ≠ error.** Component unmount / navigation is a silent clean teardown, not a transition to `error`. Wiring `AbortController` for unmount is mandatory regardless (avoids setting state after unmount and leaking the stream).
- **Widget-owned error copy, one place, consistently toned** — Layer 2's server-side error string is *not* surfaced. Drafts: `rate_limited` → *"Lots of questions coming in right now — give it a moment and try again."*; `stream`/`network` → *"Something went wrong fetching that answer."* + retry. Non-alarming inline styling, not a red crash banner.

**Deferred:** explicit user-facing **"stop" button** during streaming — the `AbortController` goes in now (for unmount), so the button is nearly free to add later.

**Cross-layer check — came back clean (no Layer 2 change):** considered whether consuming the contract wanted a machine-readable error *code* on the `error` event. It doesn't — the widget only needs to know *that* a stream errored, not *why* (`stream` is one bucket with one generic message), and the `429` is already distinguishable as a pre-stream HTTP status. Layer 2's existing friendly-string `error` event is sufficient as-is. (Flagged explicitly per the working method: "I checked whether this reaches back, and it doesn't.")

> **Implemented (`M3.5-01`).** All five decisions built in `web/components/AskWidget.tsx`. Concrete choices: **TTFB = 12s** (mid-range of the 10–15s band), armed *around the whole pre-first-event window* (a `setTimeout` set before `fetch`, so it also catches a server that hangs on response headers, not just one that opens then stalls) and cleared on the first SSE event. **Abort-reason sentinels** (`"ttfb-timeout"` vs `"unmount"`) passed to `AbortController.abort(reason)` are how the `catch` tells the two aborts apart — a timeout becomes a `network` error, an unmount stays silent (abort ≠ error). **Keep-partial** is split: the reducer already retains `answer` on `ERROR`, and `ExchangeView` shows the partial text + a muted "— the response was interrupted" note *only when tokens already rendered*, else the error copy. **Manual retry** re-sends `state.question` (retained through `ERROR`; `SUBMIT` is allowed from the settled `error` state). The two invariants this leans on — `ERROR` keeps `answer`/`question`, and `SUBMIT`-from-`error` starts fresh — are now pinned by unit tests in `lib/reducer.test.ts`. `stream` and `network` share one generic message per the copy drafts above.

---

### Decision 8 — Accessibility & responsive

**Decision (the one real call): announce the answer to screen readers on *complete*, not token-by-token.** On `done`, the full answer is written once into a hidden polite live region. Sighted users get the live token animation; screen-reader users get one coherent announcement instead of token spray, which is inconsistent and stutter-prone across assistive-tech/browser combos.

**Build spec (the non-obvious part — must be right):**

- A **visually-hidden `aria-live="polite"` region, present in the DOM from first render** (not created on submit — screen readers buffer the page, and a dynamically-injected live region needs a delay before it's reliably picked up; having it present and empty avoids that).
- **The visible streaming element is *not* the live region** — appending tokens into a live region causes per-token re-announcement / garble. The canonical fix (learned the hard way by mainstream chat widgets) is a *separate* hidden region that holds only the screen-reader text; the visible transcript is navigable separately in browse mode.
- **`polite`, never `assertive`** (assertive interrupts whatever the screen reader is saying).
- **The decline and the error states must also write into the region** — a screen-reader user must hear the decline/error, not just sighted users.

**Checklist — verify each (correctness, not decisions):**

*Keyboard & focus*
- Whole widget operable keyboard-only; logical tab order (input → send → chips → source links).
- After submit, focus does **not** jump to the top of the page (the classic chatbot focus-reset bug). Keep focus on the input; the live region carries the answer.
- Visible focus indicator on every interactive element — and confirm the host site's global CSS isn't doing `outline: none` (plausible on a messy site).

*Labels & semantics*
- Text input has a real programmatic `<label>` (visually hidden if undesired) — a placeholder is not a label.
- Send button has an accessible name (icon-only → `aria-label`).
- Suggested-question chips are real `<button>`s; "read more →" is a real `<a>` with discernible text; the "No linked page yet." note is inert.
- Disabled send uses the `disabled` attribute, not just grey styling.
- Each Q&A pair is structurally distinct (visually-hidden "You asked:" / "Answer:" prefixes or headings). Visible transcript = navigable structure; announcement = the hidden region's job — keep the two separate.

*Responsive & touch*
- Panel reflows at narrow widths (chips wrap, cards stack, transcript scrolls with touch).
- Tap targets ~44px min.
- On-screen keyboard doesn't obscure the input; internal scroll works while it's open.
- Layout survives 200% zoom / larger user font sizes without clipping.

**The one thing that must be tested *live*:** the streaming announcement can't be verified by reading code — behaviour varies across assistive tech. Test announce-on-complete with **VoiceOver** (Mac/iOS) and ideally **NVDA** (Windows). Highest-value a11y test in the layer; everything else is verifiable by inspection/keyboard.

**Deferred:** sentence-chunk announcing during the stream (richer real-time feel, cross-AT risk) — revisit only if the on-complete wait feels dead in testing; a single "Answering…" status cue is the cheaper fix if so.

> **Implemented — code side (`M3.6-01`).** In `web/components/AskWidget.tsx`: a visually-hidden `aria-live="polite" aria-atomic="true"` region rendered **from first render** (empty until settle); its text is derived to change **only** at `done` (the just-committed answer — a decline is a normal answer, so it's covered) or `error` (partial + interrupted note, else the error copy), so it announces once, never per token. The visible streaming `<p>` is **not** a live region, and the former `role="alert"` on the error line was removed (assertive) in favour of that polite region. Checklist done by inspection: hidden `<label htmlFor>` on the textarea; focus **kept on the input** after every submit (chips/Try-again unmount on send, which would otherwise drop focus to `<body>` and scroll to top); hidden "You asked:" / "Answer:" prefixes per pair; real `<button>`/`<a>` semantics + `disabled` attribute already in place; `~44px` min tap targets on send/Try-again/chips (fine visual sizing lands at `M3.7`); no `outline:none` in `app/globals.css`, so focus rings survive.
>
> **Divergence from the checklist's stated tab order (intentional, WCAG-driven).** The checklist lists "input → send → chips → source links", but this widget is **input-at-the-bottom** (chat-style): the empty-state chips and the transcript's source links render **visually above** the input. Per WCAG 2.4.3 (focus order must follow visual order), the implemented DOM/tab order is therefore **chips / source-links → input → send**, top-to-bottom — *not* input-first. Reordering the DOM to match the literal checklist would break focus-follows-visual-order, so the layout's natural order is kept. The checklist line above assumed an input-on-top layout; this note supersedes that ordering for the shipped design.
>
> **Still owed:** the live VoiceOver/NVDA pass (`M3.6-02`, MANUAL) — announce-on-complete genuinely can't be confirmed from code.

*(Contrast and `prefers-reduced-motion` are visual concerns — settled in Decision 9.)*

---

### Decision 9 — Styling & theming

**Scope:** this decision settles *strategy and isolation*, not pixels. Exact palette/spacing/visual craft is implementation-time work; choosing colours before any code would be deciding in a vacuum.

**Decisions:**

- **Style isolation: CSS Modules + a reset at the widget root.** Scoped class names stop the widget leaking *out*; an explicit reset on the widget's root element (e.g. `all: revert` or targeted resets of inherited `font`/`color`/`line-height`) stops the host's messy globals leaking *in*. Class selectors out-specify bare element selectors, catching the bulk of inbound bleed. Native to Next.js, zero config, and the hidden `aria-live` region stays in normal light DOM (well-trodden announcement path).
  - **Rejected: shadow DOM.** It's the only true two-way wall — but that wall defends against a *hostile/unknown* host, and Nic *owns* the host. The enemy here is Nic's own messy CSS, which a root reset out-specifies and which (unlike a third party's) can also just be fixed at source. Shadow DOM's costs (style injection, portal/focus quirks, library friction, the live region inside a less-tested boundary) aren't worth it for an owned host. **It defers together with the embed bundle from Decision 1, for the identical reason** — both earn their complexity only on a site Nic doesn't control.
- **Theming: the widget owns its palette via CSS custom properties on its root, overridable from the host but not dependent on it.** Coupling the widget's look to the *current* site's design tokens is fragile when the site may be rearchitected; a self-contained-but-themeable widget stays polished on its own merits (what a recruiter judges) and can be brand-matched later by overriding variables without touching internals.
  - *Rejected:* inheriting the host's tokens (fragile against a site rewrite); hardcoding with no override hook (needlessly inflexible).
- **Layout: question → answer → that pair's sources below it**, within each Q&A pair. Sources populate the instant the `sources` event lands, even while the answer area is still streaming / showing the typing indicator. The live pair sits at the bottom of the scrolling transcript.

**Commitments (a11y carry-overs + dark mode):**

- **Contrast ≥ WCAG AA** (4.5:1 body text) — a constraint on whatever palette is chosen at build time.
- **`prefers-reduced-motion` honoured** — typing-cursor blink and any fade/slide gated behind it (reduce to instant).
- **State never by colour alone** — already satisfied (error/decline carry text); holding the line.
- **Dark mode via the same CSS variables** — support `prefers-color-scheme` as default behaviour (cheap, since theming is already custom-property-based). Wiring into a *site-specific* theme toggle is deferred unless the site has one.

---

### Decision 10 — Config & deployment

Mostly mechanical — Decision 1 (first-party component) collapsed the rest.

**Decisions:**

- **API base URL is environment config, not hardcoded** — `NEXT_PUBLIC_API_BASE_URL` (the `NEXT_PUBLIC_` prefix is required for a client component to read it; build-time inlined). Local API via `.env.local` in Phase 2; the Cloudflare-fronted prod origin set in the GitHub Action's build environment for Phase 3.
- **The widget ships through the existing GitHub Action → Azure pipeline** — it's a component in the Next.js repo, so no separate bundle, no separate hosting, no cache-busting (all embed-bundle problems designed out by Decision 1). This is the Decision 1 payoff landing.
- **No secrets in the browser** (recorded property): the widget holds nothing sensitive. Pinecone and Anthropic keys live server-side on Lightsail; the only client config is the non-secret API URL.

> **Cross-layer impact (to action in Layer 2's doc):** Layer 2 locks CORS to "the site origin." Make explicit that the FastAPI allowlist must contain **both** the dev origin (`http://localhost:3000`) during Phase 2 **and** the production site origin for Phase 3 — otherwise local testing hits a CORS wall. This is a clarification of the existing contract, not a redesign. (The Cloudflare SSE-buffering pass-through check is already on Layer 2's Phase-3 checklist.)

---

### Decision 11 — Client-side ops sliver

**Decision:** Build **nothing** now; defer the entire client-side observability sliver (usage counts, client error capture) to the future Layer 4 (operational concerns).

**Rationale:** Decision 4's typed reducer already routes *every* lifecycle event (`SUBMIT / SOURCES / DELTA / DONE / ERROR`) through one dispatch point. When Layer 4 arrives, wiring in analytics or error-reporting is a localised tap at that single spot — not instrumentation threaded through the component afterward. So no unused callback prop is added now (that would be premature abstraction); the reducer *is* the hook, for free. During Phase 2 development, devtools cover client errors. Pure note-and-defer, door already open.

---

## Open Decisions

All decisions are settled. Summary:

- **Distribution:** first-party React client component; no site rewrite; embed bundle deferred.
- **Form factor:** inline panel.
- **SSE consumption:** hand-rolled `fetch` + manual SSE parser (4 parsing obligations recorded); thin parser lib and AI SDK rejected.
- **State model:** typed `useReducer`; decline = answer-with-no-sources; 429 = pre-stream branch under one discriminated `error` state; plain-text + `pre-wrap` rendering.
- **Source display:** render on arrival; group by title (display-only); compact preview + ellipsis; conditional `url` link; suppress null-note when all-null; **provenance label** (working choice "From Nic's portfolio:", honest on both answer and prompt-side-decline paths — supersedes "Based on:").
- **Interaction:** discrete-pairs transcript; suggested-question chips (from Phase-1 should-answer set); input defaults (Enter-to-send, mirrored 500-char cap, disabled-empty, disabled-in-flight).
- **Error & resilience:** TTFB-only timeout; keep partial answer; manual-only retry; abort ≠ error; widget-owned copy.
- **Accessibility:** announce on complete; hidden polite live region (present from first render, separate from visible element); full checklist; live SR test required.
- **Styling:** CSS Modules + root reset (shadow DOM deferred); own-but-overridable custom-property palette; Q→A→Sources layout; AA contrast, reduced-motion, dark mode via vars.
- **Config:** env-based API URL; existing GitHub Action → Azure; no browser secrets.
- **Ops sliver:** deferred to Layer 4 (reducer is the future hook).

---

## Libraries & Dependencies

The notable feature of this layer's dependency list is how **short** it is — deliberately.

| Package | Purpose |
| --- | --- |
| `react` / `next` | The host app — already present; the widget is a first-party client component |
| (none for SSE) | SSE consumption is hand-rolled `fetch` + manual parser (Decision 3) |
| (none for styling) | CSS Modules is built into Next.js; no CSS-in-JS or UI library |
| (none for state) | Native `useReducer`; no state-machine library |
| (none for markdown) | Plain-text rendering; markdown renderer deferred |
| (none for a11y) | Native ARIA (`aria-live`, labels); no a11y library |

> Deliberately *not* added: a thin SSE parser lib, the Vercel AI SDK, a markdown renderer, XState, a component library — each considered and rejected or deferred above.

---

## Open Questions / Next Steps

All design decisions are settled; remaining work is implementation.

- [ ] Build the widget as a `'use client'` component in the Next.js repo (inline panel)
- [ ] Implement the hand-rolled `fetch` + SSE parser, honouring the four obligations (cross-chunk buffering, named-event association, streaming UTF-8 decode, comment-line skip)
- [ ] Implement the `useReducer` state machine (`idle/submitting/streaming/done/error{kind}`; events `SUBMIT/SOURCES/DELTA/DONE/ERROR/RESET`)
- [ ] Render: plain-text `pre-wrap` streaming answer; discrete-pairs bounded scrolling transcript; grouped source cards with preview + ellipsis under a **provenance label** (working choice "From Nic's portfolio:"); conditional "read more →"; suppress null-note when all-null
- [x] Suggested-question chips in the empty state, sourced from Layer 2's Phase-1 should-answer set — `web/lib/chips.ts` + `AskWidget.tsx` (`M3.4-01`; live-validated, 2 weak candidates dropped)
- [x] Input: Enter-to-send; client-side 500-char cap + counter; disabled on empty/whitespace; disabled while in flight — `AskWidget.tsx` (`M3.4-01`)
- [x] Error handling: TTFB timeout (~10–15s); keep partial answer + interrupted note; manual "Try again"; `AbortController` teardown on unmount; widget-owned error copy — `AskWidget.tsx` (`M3.5-01`)
- [~] Accessibility: hidden polite live region (present from first render); work the full checklist — code side done in `AskWidget.tsx` (`M3.6-01`); **live announce-on-complete test with VoiceOver + NVDA still owed (`M3.6-02`, MANUAL/Nic)**
- [ ] Styling: CSS Modules + root reset; custom-property palette (overridable); AA contrast; `prefers-reduced-motion`; dark mode via `prefers-color-scheme`
- [ ] Config: `NEXT_PUBLIC_API_BASE_URL` (`.env.local` dev / Action build env prod)
- [ ] **Cross-layer:** ensure Layer 2's CORS allowlist includes the dev origin (`localhost:3000`, Phase 2) and the prod site origin (Phase 3) — note added to `L2_Query_Pipeline.md`
- [ ] Deploy via the existing GitHub Action → Azure (Phase 3); verify streaming end-to-end through Cloudflare (no `text/event-stream` buffering)
