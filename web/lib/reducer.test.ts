import { expect, it } from "vitest";

import { type State, initialState, reducer } from "./reducer";
import type { Source } from "./types";

const SRC: Source = { title: "A", text: "alpha", url: null, anchor: null };

it("SUBMIT from idle -> submitting and clears any prior answer", () => {
  const s = reducer({ ...initialState, answer: "old" }, { type: "SUBMIT", question: "q1" });
  expect(s.status).toBe("submitting");
  expect(s.question).toBe("q1");
  expect(s.answer).toBe("");
});

it("ignores SUBMIT while streaming (no overlapping streams)", () => {
  const streaming: State = { ...initialState, status: "streaming", answer: "partial" };
  expect(reducer(streaming, { type: "SUBMIT", question: "q2" })).toBe(streaming);
});

it("SOURCES then DELTA accumulate and enter streaming", () => {
  let s = reducer(initialState, { type: "SUBMIT", question: "q" });
  s = reducer(s, { type: "SOURCES", sources: [SRC] });
  expect(s.status).toBe("streaming");
  expect(s.sources).toEqual([SRC]);
  s = reducer(s, { type: "DELTA", text: "Hello " });
  s = reducer(s, { type: "DELTA", text: "world" });
  expect(s.answer).toBe("Hello world");
});

it("DONE commits the pair to the transcript and clears the live fields", () => {
  let s = reducer(initialState, { type: "SUBMIT", question: "q" });
  s = reducer(s, { type: "DELTA", text: "answer" });
  s = reducer(s, { type: "DONE" });
  expect(s.status).toBe("done");
  expect(s.transcript).toEqual([{ question: "q", answer: "answer", sources: [] }]);
  expect(s.answer).toBe("");
});

it("a decline (delta + done, no sources) is just an answer — no special state", () => {
  let s = reducer(initialState, { type: "SUBMIT", question: "weather?" });
  s = reducer(s, { type: "DELTA", text: "Sorry, I don't have information about that." });
  s = reducer(s, { type: "DONE" });
  expect(s.transcript[0].sources).toEqual([]);
  expect(s.transcript[0].answer).toContain("Sorry");
});

it("ERROR sets a discriminated kind", () => {
  const s = reducer({ ...initialState, status: "submitting" }, { type: "ERROR", kind: "rate_limited" });
  expect(s.status).toBe("error");
  expect(s.error).toBe("rate_limited");
});

it("SUBMIT after done starts fresh but keeps the transcript", () => {
  let s = reducer(initialState, { type: "SUBMIT", question: "q1" });
  s = reducer(s, { type: "DELTA", text: "a1" });
  s = reducer(s, { type: "DONE" });
  s = reducer(s, { type: "SUBMIT", question: "q2" });
  expect(s.status).toBe("submitting");
  expect(s.transcript).toHaveLength(1);
});
