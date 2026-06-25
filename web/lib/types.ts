/** Shared widget types. `Source` mirrors the SSE `sources` event payload (url/anchor nullable). */

export interface Source {
  title: string;
  text: string;
  url: string | null;
  anchor: string | null;
}

/** A completed question → answer → sources triple. Kept client-side only — never sent back. */
export interface Exchange {
  question: string;
  answer: string;
  sources: Source[];
}
