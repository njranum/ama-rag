"use client";

/**
 * Inline ask-me-anything widget (M3.1-01 scaffold; M3.2 state + rendering).
 *
 * A first-party `'use client'` component (streaming forces client-side) mounted inline in the page
 * flow. State is driven by a typed `useReducer` machine (M3.2-01 / L3 D4); the answer renders as
 * plain text with `white-space: pre-wrap` and completed Q→A→Sources pairs accumulate in a bounded,
 * internally-scrolling transcript (M3.2-02 / L3 D4+D6). Later slices refine it: source cards (M3.3),
 * error policy + abort/timeout (M3.5), accessibility (M3.6), CSS-Modules styling (M3.7).
 */

import { type FormEvent, useReducer, useRef, useState } from "react";

import SourceCards from "@/components/SourceCards";
import { type ErrorKind, initialState, reducer } from "@/lib/reducer";
import { parseSseStream } from "@/lib/sse";
import type { Source } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const ERROR_COPY: Record<ErrorKind, string> = {
  rate_limited: "You're asking a little quickly — give it a moment and try again.",
  stream: "Something went wrong generating an answer. Please try again.",
  network: "Couldn't reach the server. Check your connection and try again.",
};

function ExchangeView({
  question,
  answer,
  sources,
  pending = false,
  errorText = null,
}: {
  question: string;
  answer: string;
  sources: Source[];
  pending?: boolean;
  errorText?: string | null;
}) {
  return (
    <div>
      <p style={{ fontWeight: 600, margin: "0 0 0.25rem" }}>{question}</p>
      {errorText ? (
        <p role="alert" style={{ color: "#b00020", margin: 0 }}>
          {errorText}
        </p>
      ) : (
        <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{answer || (pending ? "…" : "")}</p>
      )}
      <SourceCards sources={sources} />
    </div>
  );
}

export default function AskWidget() {
  const [question, setQuestion] = useState("");
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<AbortController | null>(null);

  const busy = state.status === "submitting" || state.status === "streaming";

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const q = question.trim();
    if (!q || busy) return;
    setQuestion("");
    dispatch({ type: "SUBMIT", question: q });

    const controller = new AbortController();
    abortRef.current = controller;
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
        if (evt.event === "sources") {
          dispatch({ type: "SOURCES", sources: JSON.parse(evt.data).sources as Source[] });
        } else if (evt.event === "delta") {
          const { text } = JSON.parse(evt.data) as { text: string };
          dispatch({ type: "DELTA", text });
        } else if (evt.event === "done") {
          dispatch({ type: "DONE" });
        } else if (evt.event === "error") {
          dispatch({ type: "ERROR", kind: "stream" });
        }
      }
    } catch {
      dispatch({ type: "ERROR", kind: "network" });
    }
  }

  const showLive = state.status !== "idle" && state.status !== "done";
  const isEmpty = state.transcript.length === 0 && !showLive;

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
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
            errorText={state.status === "error" ? ERROR_COPY[state.error ?? "stream"] : null}
          />
        )}
        {isEmpty && <p style={{ color: "#666", margin: 0 }}>Ask a question to get started.</p>}
      </div>

      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          maxLength={500}
          placeholder="What would you like to know?"
          style={{ width: "100%", padding: "0.5rem", fontFamily: "inherit" }}
        />
        <button
          type="submit"
          disabled={busy || !question.trim()}
          style={{ alignSelf: "flex-start" }}
        >
          {busy ? "Asking…" : "Ask"}
        </button>
      </form>
    </section>
  );
}
