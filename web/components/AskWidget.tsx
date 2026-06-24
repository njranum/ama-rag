"use client";

/**
 * Inline ask-me-anything widget (M3.1-01 scaffold; M3.2 state + rendering).
 *
 * A first-party `'use client'` component (streaming forces client-side) mounted inline in the page
 * flow. State is driven by a typed `useReducer` machine (M3.2-01 / L3 D4); the answer renders as
 * plain text with `white-space: pre-wrap` and completed Q→A→Sources pairs accumulate in a bounded,
 * internally-scrolling transcript (M3.2-02 / L3 D4+D6). Source cards (M3.3); empty-state chips +
 * input defaults (M3.4 / L3 D6); client error & resilience — TTFB timeout, keep-partial, manual
 * retry, abort-on-unmount (M3.5 / L3 D7); a11y — hidden polite live region announcing the settled
 * answer/decline/error once, label, focus-stays-on-input, structural prefixes (M3.6 / L3 D8).
 * Later slice: CSS-Modules styling, contrast, reduced-motion (M3.7).
 */

import { type FormEvent, type KeyboardEvent, useEffect, useReducer, useRef, useState } from "react";

import SourceCards from "@/components/SourceCards";
import { announcementText } from "@/lib/announce";
import { SUGGESTED_QUESTIONS } from "@/lib/chips";
import { type ErrorKind, initialState, reducer } from "@/lib/reducer";
import { parseSseStream } from "@/lib/sse";
import type { Source } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const MAX_CHARS = 500; // mirror the server cap (config.MAX_QUESTION_CHARS) — feedback, not a 400
const COUNTER_FROM = 450; // start surfacing the counter as the limit approaches

// Time-to-first-event timeout (L3 D7): a backstop for a hung server that never sends the first
// `sources` event. Once events flow we clear it and never time out on duration — deltas arriving
// IS the health signal, so a healthy long answer is never guillotined.
const TTFB_TIMEOUT_MS = 12_000;

// Abort reasons, so the catch can tell WHY a stream was aborted (L3 D7): a TTFB timeout is a real
// `network` error to surface; an unmount/navigation teardown is silent (abort ≠ error).
const ABORT_TIMEOUT = "ttfb-timeout";
const ABORT_UNMOUNT = "unmount";

// Widget-owned copy (L3 D7) — Layer 2's server-side error string is never surfaced. One place,
// consistently and non-alarmingly toned. `stream` and `network` share the generic message.
const ERROR_COPY: Record<ErrorKind, string> = {
  rate_limited: "Lots of questions coming in right now — give it a moment and try again.",
  stream: "Something went wrong fetching that answer.",
  network: "Something went wrong fetching that answer.",
};

// Visually-hidden but available to assistive tech (the standard sr-only recipe) — used for the
// input label, the structural "You asked:"/"Answer:" prefixes, and the live announcement region.
const srOnly: React.CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0, 0, 0, 0)",
  whiteSpace: "nowrap",
  border: 0,
};

function ExchangeView({
  question,
  answer,
  sources,
  pending = false,
  error = null,
}: {
  question: string;
  answer: string;
  sources: Source[];
  pending?: boolean;
  error?: ErrorKind | null;
}) {
  // Keep-partial (L3 D7): if tokens already rendered and then an error arrives, keep the real,
  // grounded text and append a muted interruption note — discarding it reads as more broken than
  // the interruption. Only when nothing streamed yet do we replace with the error copy.
  const interrupted = error !== null && answer.length > 0;
  // Each pair is structurally distinct for browse-mode navigation (L3 D8). The visible elements are
  // NOT live regions — announcement is the hidden region's job, so a screen reader hears the answer
  // once on completion rather than token-by-token. Error copy is a plain styled <p> (not role=alert,
  // which is assertive) — the polite region carries it to AT instead.
  return (
    <div>
      <p style={{ fontWeight: 600, margin: "0 0 0.25rem" }}>
        <span style={srOnly}>You asked: </span>
        {question}
      </p>
      {error !== null && answer.length === 0 ? (
        <p style={{ color: "#b00020", margin: 0 }}>{ERROR_COPY[error]}</p>
      ) : (
        <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
          <span style={srOnly}>Answer: </span>
          {answer || (pending ? "…" : "")}
          {interrupted && <span style={{ color: "#888" }}> — the response was interrupted</span>}
        </p>
      )}
      <SourceCards sources={sources} />
    </div>
  );
}

export default function AskWidget() {
  const [question, setQuestion] = useState("");
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const busy = state.status === "submitting" || state.status === "streaming";

  // Single entry point for both the form and the suggested-question chips (populate-and-send).
  async function ask(raw: string) {
    const q = raw.trim();
    if (!q || busy) return;
    setQuestion("");
    dispatch({ type: "SUBMIT", question: q });
    // Keep focus on the input after submit (L3 D8) — chips/Try-again unmount on send, which would
    // otherwise drop focus to <body> and scroll the page to the top (the classic chatbot bug). The
    // textarea is always mounted, so this is safe even from a chip click.
    inputRef.current?.focus();

    const controller = new AbortController();
    abortRef.current = controller;
    // Arm the TTFB timeout around the whole pre-first-event window (covers a fetch that hangs on
    // headers AND a connection that opens but never sends `sources`). Cleared on the first event.
    let firstEventSeen = false;
    const timeoutId = setTimeout(() => controller.abort(ABORT_TIMEOUT), TTFB_TIMEOUT_MS);

    try {
      const res = await fetch(`${API_BASE}/v1/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
        signal: controller.signal,
      });
      // 429 arrives pre-stream — branch on status before touching the body (L3 D4).
      if (res.status === 429) {
        dispatch({ type: "ERROR", kind: "rate_limited" });
        return;
      }
      if (!res.ok || !res.body) {
        dispatch({ type: "ERROR", kind: "stream" });
        return;
      }
      for await (const evt of parseSseStream(res.body)) {
        if (!firstEventSeen) {
          firstEventSeen = true;
          clearTimeout(timeoutId); // first event arrived — trust the stream from here (L3 D7)
        }
        if (evt.event === "sources") {
          dispatch({ type: "SOURCES", sources: JSON.parse(evt.data).sources as Source[] });
        } else if (evt.event === "delta") {
          const { text } = JSON.parse(evt.data) as { text: string };
          dispatch({ type: "DELTA", text });
        } else if (evt.event === "done") {
          dispatch({ type: "DONE" });
        } else if (evt.event === "error") {
          dispatch({ type: "ERROR", kind: "stream" }); // keep-partial: reducer retains `answer`
          break; // error is terminal — stop reading and release the stream
        }
      }
    } catch {
      // Abort ≠ error (L3 D7): a silent unmount teardown must not flash an error; a TTFB timeout
      // is a real `network` error to surface. Any non-abort throw is a genuine network failure.
      if (controller.signal.aborted) {
        if (controller.signal.reason === ABORT_TIMEOUT) {
          dispatch({ type: "ERROR", kind: "network" });
        }
      } else {
        dispatch({ type: "ERROR", kind: "network" });
      }
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // Abort an in-flight stream on unmount/navigation — a silent clean teardown (reason = unmount,
  // so the catch stays quiet), which also prevents set-state-after-unmount and a leaked reader.
  useEffect(() => () => abortRef.current?.abort(ABORT_UNMOUNT), []);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  // Enter sends; Shift+Enter keeps a newline. Mirrors the send button's settled-state guard.
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void ask(question);
    }
  }

  const showLive = state.status !== "idle" && state.status !== "done";
  const isEmpty = state.transcript.length === 0 && !showLive;
  const remaining = MAX_CHARS - question.length;

  // Announce the SETTLED result once (L3 D8) — empty during submitting/streaming, so the polite
  // region fires exactly once at settle, never per token. See lib/announce.ts.
  const announcement = announcementText(state, ERROR_COPY);

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {/* Present and empty from first render (L3 D8) — a dynamically-injected live region needs a
          delay before AT picks it up. polite + atomic so the whole settled answer is one coherent
          announcement, never the assertive interrupt. */}
      <div aria-live="polite" aria-atomic="true" style={srOnly}>
        {announcement}
      </div>
      <div
        style={{
          maxHeight: 360,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
          padding: "0.75rem",
          border: "1px solid #ddd",
          borderRadius: 8,
        }}
      >
        {state.transcript.map((ex, i) => (
          <ExchangeView key={i} question={ex.question} answer={ex.answer} sources={ex.sources} />
        ))}
        {showLive && (
          <ExchangeView
            question={state.question}
            answer={state.answer}
            sources={state.sources}
            pending={state.status === "submitting"}
            error={state.status === "error" ? (state.error ?? "stream") : null}
          />
        )}
        {state.status === "error" && (
          <button
            type="button"
            onClick={() => void ask(state.question)}
            style={{ alignSelf: "flex-start", minHeight: 44 }}
          >
            Try again
          </button>
        )}
        {isEmpty && (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <p style={{ color: "#666", margin: 0 }}>Ask a question to get started, or try one of these:</p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => void ask(q)}
                  disabled={busy}
                  style={{
                    minHeight: 44,
                    padding: "0.4rem 0.85rem",
                    border: "1px solid #ccc",
                    borderRadius: 999,
                    background: "#f6f6f6",
                    cursor: busy ? "default" : "pointer",
                    fontSize: "0.85rem",
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <label htmlFor="ask-input" style={srOnly}>
          Ask a question about Marlowe
        </label>
        <textarea
          id="ask-input"
          ref={inputRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          rows={3}
          maxLength={MAX_CHARS}
          placeholder="What would you like to know?"
          style={{ width: "100%", padding: "0.5rem", fontFamily: "inherit" }}
        />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.5rem",
          }}
        >
          <button type="submit" disabled={busy || !question.trim()} style={{ minHeight: 44 }}>
            {busy ? "Asking…" : "Ask"}
          </button>
          {question.length >= COUNTER_FROM && (
            <span
              aria-live="polite"
              style={{ fontSize: "0.8rem", color: remaining <= 0 ? "#b00020" : "#666" }}
            >
              {remaining} characters left
            </span>
          )}
        </div>
      </form>
    </section>
  );
}
