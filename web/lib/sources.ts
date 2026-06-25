import type { Source } from "@/lib/types";

/**
 * Display-only group-by-title (M3.3-01, L3 Decision 5). With k=4 and ~50-token chunk overlap,
 * several retrieved chunks often come from the same page; rendered flat that's repeated identical
 * titles (reads as broken). Collapse to one card per title. The array is best-match-first, so the
 * first chunk per title represents the group. (Distinct from L2's deferred *retrieval*-level dedup.)
 */
export function groupByTitle(sources: Source[]): Source[] {
  const seen = new Set<string>();
  const grouped: Source[] = [];
  for (const source of sources) {
    if (seen.has(source.title)) continue;
    seen.add(source.title);
    grouped.push(source);
  }
  return grouped;
}
