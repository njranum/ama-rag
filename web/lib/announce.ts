/**
 * Screen-reader announcement text for the hidden polite live region (M3.6-01, L3 D8).
 *
 * Derived from state so it changes ONLY at a settled status — `done` or `error` — and is empty
 * while `submitting`/`streaming`. That is what makes the region announce the answer exactly once,
 * coherently, instead of token-by-token (which garbles across assistive-tech/browser combos).
 *
 * A decline is a normal `delta`+`done`, so it lands in the transcript and is announced like any
 * answer; an error announces the kept partial (+ interrupted note) or, if nothing streamed, the
 * widget-owned error copy. Both decline and error must reach AT, not just sighted users (L3 D8).
 */

import type { ErrorKind, State } from "./reducer";

export function announcementText(state: State, errorCopy: Record<ErrorKind, string>): string {
  if (state.status === "done") {
    const last = state.transcript[state.transcript.length - 1];
    return last ? `Answer: ${last.answer}` : "";
  }
  if (state.status === "error") {
    return state.answer
      ? `${state.answer} — the response was interrupted`
      : errorCopy[state.error ?? "stream"];
  }
  return "";
}
