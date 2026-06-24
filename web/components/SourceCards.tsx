/**
 * Source cards (M3.3-01, L3 Decision 5).
 *
 * Rendered from the `sources` event. Grouped by page title (display-only), each a line-clamped
 * `…preview…` excerpt under an honest **provenance** label ("From Nic's portfolio:") — a provenance
 * claim, not a causation one, so it reads coherently above both an answer and a prompt-side decline
 * without any decline detection. "read more →" appears only when `url` is non-null; the muted
 * "No linked page yet." note shows only in the mixed state (some linked, some not), never when all
 * urls are null (the clean pre-C2 launch state). Renders nothing for an empty source set (so a gate
 * decline shows no empty sources header).
 */

import { groupByTitle } from "@/lib/sources";
import type { Source } from "@/lib/types";

const PROVENANCE_LABEL = "From Nic's portfolio:";

const previewStyle: React.CSSProperties = {
  fontSize: "0.8rem",
  color: "#555",
  margin: 0,
  display: "-webkit-box",
  WebkitLineClamp: 2,
  WebkitBoxOrient: "vertical",
  overflow: "hidden",
};

export default function SourceCards({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;
  const cards = groupByTitle(sources);
  const allNull = cards.every((c) => c.url === null);

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <p style={{ fontSize: "0.8rem", color: "#666", margin: "0 0 0.4rem" }}>{PROVENANCE_LABEL}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {cards.map((c, i) => (
          <article
            key={`${c.title}-${i}`}
            style={{ border: "1px solid #e3e3e3", borderRadius: 6, padding: "0.5rem 0.6rem" }}
          >
            <p style={{ fontWeight: 600, fontSize: "0.85rem", margin: "0 0 0.2rem" }}>{c.title}</p>
            <p style={previewStyle}>…{c.text}</p>
            {c.url ? (
              <a
                href={c.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: "0.8rem" }}
              >
                read more →
              </a>
            ) : (
              !allNull && (
                <span style={{ fontSize: "0.75rem", color: "#999" }}>No linked page yet.</span>
              )
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
