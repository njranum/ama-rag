/**
 * Empty-state suggested-question chips (M3.4-01, L3 Decision 6).
 *
 * A curated subset of Layer 2's Phase-1 **should-answer** eval set (`query/eval_set.py`, M2.2-01) —
 * questions already verified to be covered by the indexed content, so a chip never demos a decline.
 * The eval set lives in the Python backend and can't be imported across the layer boundary, so this
 * is a hand-picked, provenance-tagged copy rather than a runtime import.
 *
 * Selection: each of these was exercised live against the local FastAPI + Chroma stack and returned
 * a STRONG grounded answer (gate cleared + a real answer, not a hedge). Candidates that answered
 * weakly on the synthetic corpus were dropped — "Where does Marlowe currently work?" (retrieval
 * missed Orrery) and "What open source work has Marlowe done?" (hedged decline). The four kept span
 * project / skills / hiring-fit / origin-story for a varied first impression.
 *
 * PROVISIONAL — grounded in the synthetic Marlowe Finch corpus; re-pick from the regenerated
 * should-answer set when real content lands at M4.2-03 (re-validate live before shipping).
 */

export const SUGGESTED_QUESTIONS: readonly string[] = [
  "What is the Tideline project?",
  "What programming languages does Marlowe use?",
  "What kind of role is Marlowe looking for?",
  "What did Marlowe do before becoming a software engineer?",
];
