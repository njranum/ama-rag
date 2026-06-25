"use client";

/**
 * Source cards (M3.3-01, L3 Decision 5; styled via CSS Modules at M3.7-01 / L3 D9).
 *
 * Rendered from the `sources` event. On arrival the component shows a single compact **summary
 * line** — the inverted **provenance** tag ("From Nic's portfolio") + a source count + a chevron —
 * which doubles as the loading-state exit / "found these, now composing" cue (Decision 5's
 * render-on-arrival intent). The line is a real <button> (aria-expanded / aria-controls); expanding
 * reveals the grouped cards. Collapsed by default so a long answer and the cards no longer compete
 * for one height-capped box (the answer block now owns the height cap — L3 D2).
 *
 * Each card: grouped by page title (display-only), a line-clamped `…preview…` excerpt. The label is
 * a provenance claim, not a causation one, so it reads coherently above both an answer and a
 * prompt-side decline without any decline detection. "read more →" appears only when `url` is
 * non-null; the muted "No linked page yet." note shows only in the mixed state (some linked, some
 * not), never when all urls are null (the clean pre-C2 launch state). Renders nothing for an empty
 * source set (so a gate decline shows no summary line at all).
 */

import { useId, useState } from "react";

import styles from "@/components/SourceCards.module.css";
import { groupByTitle } from "@/lib/sources";
import type { Source } from "@/lib/types";

// Provenance assertion, not causation (L3 D5). No trailing colon — a count follows it on the line.
const PROVENANCE_LABEL = "From Nic's portfolio";

export default function SourceCards({ sources }: { sources: Source[] }) {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  if (sources.length === 0) return null;
  const cards = groupByTitle(sources);
  const allNull = cards.every((c) => c.url === null);
  const count = cards.length;

  return (
    <div className={styles.sources}>
      <button
        type="button"
        className={styles.summary}
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Inverted block — provenance tag. Real sentence-case text uppercased in CSS so AT never
            spells out the caps. */}
        <span className={styles.provenance}>{PROVENANCE_LABEL}</span>
        <span className={styles.count}>
          · {count} {count === 1 ? "source" : "sources"}
        </span>
        <span className={styles.chevron} aria-hidden="true">
          {expanded ? "▾" : "▸"}
        </span>
      </button>
      {/* Always rendered (keeps aria-controls valid); [hidden] collapses it to nothing. */}
      <div id={panelId} className={styles.cardList} hidden={!expanded}>
        {cards.map((c, i) => (
          <article key={`${c.title}-${i}`} className={styles.card}>
            <div className={styles.cardHead}>
              {/* Decorative archive record index (mono). Hidden from AT so a screen reader hears
                  the title, not "zero-one Tideline…". */}
              <span className={styles.cardIndex} aria-hidden="true">
                {String(i + 1).padStart(2, "0")}
              </span>
              <p className={styles.cardTitle}>{c.title}</p>
            </div>
            {/* Leading + trailing ellipsis marks the chunk as an excerpt (L3 D5). */}
            <p className={styles.preview}>…{c.text}…</p>
            {c.url ? (
              <a className={styles.readMore} href={c.url} target="_blank" rel="noopener noreferrer">
                read more →
              </a>
            ) : (
              !allNull && <span className={styles.noLink}>No linked page yet.</span>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
