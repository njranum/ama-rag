"use client";

/**
 * Inline ask-me-anything widget — M3.1-01 scaffold (L3 Decisions 1, 2, 10).
 *
 * A first-party `'use client'` component (streaming forces client-side) that mounts inline in the
 * page flow. It reads the non-secret API base URL from `NEXT_PUBLIC_API_BASE_URL` and consumes the
 * /v1/ask SSE contract via the hand-rolled parser (M3.1-02).
 *
 * This is the minimal scaffold: a basic useState model proves the parser + streaming end-to-end.
 * Later slices refine it — useReducer state machine (M3.2), source cards (M3.3), error policy
 * (M3.5), accessibility (M3.6), and styling/CSS Modules (M3.7).
 */

import { type FormEvent, useRef, useState } from "react";

import { parseSseStream } from "@/lib/sse";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface Source {
  title: string;
  text: string;
  url: string | null;
  anchor: string | null;
}

type Status = "idle" | "streaming" | "error";

export default function AskWidget() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const abortRef = useRef<AbortController | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const q = question.trim();
    if (!q || status === "streaming") return;

    setAnswer("");
    setSources([]);
    setStatus("streaming");
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_BASE}/v1/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
        signal: controller.signal,
      });
      // Check status before reading the body — the 429 branch arrives pre-stream (M3.5-01).
      if (res.status === 429 || !res.ok || !res.body) {
        setStatus("error");
        return;
      }
      for await (const evt of parseSseStream(res.body)) {
        if (evt.event === "sources") {
          setSources(JSON.parse(evt.data).sources as Source[]);
        } else if (evt.event === "delta") {
          const { text } = JSON.parse(evt.data) as { text: string };
          setAnswer((prev) => prev + text);
        } else if (evt.event === "error") {
          setStatus("error");
          return;
        }
      }
      setStatus((prev) => (prev === "error" ? prev : "idle"));
    } catch {
      setStatus("error");
    }
  }

  return (
    <section>
      <form onSubmit={onSubmit}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          maxLength={500}
          placeholder="What would you like to know?"
          style={{ width: "100%" }}
        />
        <button type="submit" disabled={status === "streaming" || !question.trim()}>
          {status === "streaming" ? "Asking…" : "Ask"}
        </button>
      </form>

      {status === "error" && <p role="alert">Something went wrong. Please try again.</p>}
      {answer && <p style={{ whiteSpace: "pre-wrap" }}>{answer}</p>}

      {sources.length > 0 && (
        <ul>
          {sources.map((s, i) => (
            <li key={`${s.title}-${i}`}>{s.title}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
