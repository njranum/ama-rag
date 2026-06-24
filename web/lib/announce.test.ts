import { expect, it } from "vitest";

import { announcementText } from "./announce";
import { type ErrorKind, type State, initialState } from "./reducer";

const COPY: Record<ErrorKind, string> = {
  rate_limited: "rate limited copy",
  stream: "generic error copy",
  network: "generic error copy",
};

it("is empty while submitting or streaming (no per-token announcement) — M3.6", () => {
  expect(announcementText({ ...initialState, status: "submitting" }, COPY)).toBe("");
  expect(announcementText({ ...initialState, status: "streaming", answer: "half" }, COPY)).toBe("");
});

it("announces the just-committed answer once on done — M3.6", () => {
  const s: State = {
    ...initialState,
    status: "done",
    transcript: [{ question: "q", answer: "the full answer", sources: [] }],
  };
  expect(announcementText(s, COPY)).toBe("Answer: the full answer");
});

it("announces a decline like any answer (decline is delta+done) — M3.6", () => {
  const s: State = {
    ...initialState,
    status: "done",
    transcript: [{ question: "weather?", answer: "Sorry, I don't have information about that.", sources: [] }],
  };
  expect(announcementText(s, COPY)).toContain("Sorry");
});

it("announces kept partial + interrupted note on mid-stream error — M3.6", () => {
  const s: State = { ...initialState, status: "error", error: "stream", answer: "partial text" };
  expect(announcementText(s, COPY)).toBe("partial text — the response was interrupted");
});

it("announces the widget-owned error copy when nothing streamed — M3.6", () => {
  const s: State = { ...initialState, status: "error", error: "rate_limited", answer: "" };
  expect(announcementText(s, COPY)).toBe("rate limited copy");
});
