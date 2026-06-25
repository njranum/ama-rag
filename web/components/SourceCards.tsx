/**
 * Source cards (M3.3-01, L3 Decision 5; styled via CSS Modules at M3.7-01 / L3 D9).
 *
 * Rendered from the `sources` event. Grouped by page title (display-only), each a line-clamped
 * `…preview…` excerpt under an honest **provenance** label ("From Nic's portfolio:") — a provenance
 * claim, not a causation one, so it reads coherently above both an answer and a prompt-side decline
 * without any decline detection. "read more →" appears only when `url` is non-null; the muted
 * "No linked page yet." note shows only in the mixed state (some linked, some not), never when all
 * urls are null (the clean pre-C2 launch state). Renders nothing for an empty source set (so a gate
 * decline shows no empty sources header).
 */

import styles from "@/components/SourceCards.module.css";
import { groupByTitle } from "@/lib/sources";
import type { Source } from "@/lib/types";

const PROVENANCE_LABEL = "From Nic's portfolio:";

export default function SourceCards({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;
  const cards = groupByTitle(sources);
  const allNull = cards.every((c) => c.url === null);

  return (
    <div className={styles.sources}>
      <p className={styles.provenance}>{PROVENANCE_LABEL}</p>
      <div className={styles.cardList}>
        {cards.map((c, i) => (
          <article key={`${c.title}-${i}`} className={styles.card}>
            <p className={styles.cardTitle}>{c.title}</p>
            <p className={styles.preview}>…{c.text}</p>
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
