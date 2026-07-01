/**
 * Empty-state suggested-question chips (M3.4-01, L3 Decision 6).
 *
 * A curated subset of Layer 2's Phase-1 **should-answer** eval set (`query/eval_set.py`, M2.2-01) —
 * questions already verified to be covered by the indexed content, so a chip never demos a decline.
 * The eval set lives in the Python backend and can't be imported across the layer boundary, so this
 * is a hand-picked, provenance-tagged copy rather than a runtime import.
 *
 * Selection: each is drawn from the regenerated real should-answer set and clears the relevance
 * gate with margin on the real corpus (M4.2-03 calibration: Gentrack 0.50, languages 0.57, role
 * 0.46, Fix My Vibe 0.54 — all well above the 0.375 gate), so a chip never demos a decline. The
 * four span experience / skills / hiring-fit / a signature project for a varied first impression.
 *
 * Regenerated from the synthetic Marlowe Finch set at the M4.2-03 content swap. The eval set lives
 * in the Python backend and can't be imported across the layer boundary, so this is a hand-picked,
 * provenance-tagged copy rather than a runtime import.
 */

export const SUGGESTED_QUESTIONS: readonly string[] = [
  "What did Nic do at Gentrack?",
  "What programming languages is Nic strongest in?",
  "What kind of role is Nic looking for?",
  "What is Fix My Vibe?",
];
