/**
 * Typed widget state machine (M3.2-01, L3 Decision 4).
 *
 * One `status` discriminated union — `idle → submitting → streaming → done`, plus a terminal
 * `error` carrying a discriminated `kind`. This avoids "boolean soup" (isLoading/isStreaming/
 * isError), which permits impossible states. The reducer is the single tap point for any future
 * ops instrumentation (Layer 4).
 *
 * Two design rules baked in here:
 *  - The **decline is not a special state** — it arrives as a normal `delta` + `done` and flows
 *    through the same path as any answer. We never string-match the canned wording.
 *  - **Submit is only allowed from a settled state** (idle/done/error) — never mid-stream — so
 *    overlapping streams can't happen.
 */

import type { Exchange, Source } from "@/lib/types";

export type Status = "idle" | "submitting" | "streaming" | "done" | "error";
export type ErrorKind = "rate_limited" | "stream" | "network";

export interface State {
  status: Status;
  question: string;
  answer: string;
  sources: Source[];
  error: ErrorKind | null;
  transcript: Exchange[];
}

export type Action =
  | { type: "SUBMIT"; question: string }
  | { type: "SOURCES"; sources: Source[] }
  | { type: "DELTA"; text: string }
  | { type: "DONE" }
  | { type: "ERROR"; kind: ErrorKind }
  | { type: "RESET" };

export const initialState: State = {
  status: "idle",
  question: "",
  answer: "",
  sources: [],
  error: null,
  transcript: [],
};

const SETTLED: ReadonlySet<Status> = new Set<Status>(["idle", "done", "error"]);

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "SUBMIT":
      if (!SETTLED.has(state.status)) return state; // guard: no overlapping streams
      return {
        ...state,
        status: "submitting",
        question: action.question,
        answer: "",
        sources: [],
        error: null,
      };
    case "SOURCES":
      return { ...state, status: "streaming", sources: action.sources };
    case "DELTA":
      return { ...state, status: "streaming", answer: state.answer + action.text };
    case "DONE":
      // Commit the completed pair to the transcript, then clear the live fields.
      return {
        ...state,
        status: "done",
        question: "",
        answer: "",
        sources: [],
        transcript: [
          ...state.transcript,
          { question: state.question, answer: state.answer, sources: state.sources },
        ],
      };
    case "ERROR":
      return { ...state, status: "error", error: action.kind };
    case "RESET":
      return initialState;
    default:
      return state;
  }
}
