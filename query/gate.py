"""Layer 2 — hybrid relevance gate (M2.1-02).

If the best retrieved chunk's similarity is below the configured threshold, the query is treated as
off-topic: the pipeline returns a fixed bare decline **without calling the LLM** — cheap,
zero-hallucination, and a shield against off-topic abuse / prompt injection (hostile text never
reaches the model). The threshold lives in config and is calibrated empirically in M2.2-02. See
docs/L2_Query_Pipeline.md (relevance gate).
"""

from __future__ import annotations

import config
from query.retrieval import RetrievedChunk

# Same bare-but-polite wording as the prompt-side decline (M2.3), for consistency.
DECLINE_MESSAGE = "Sorry, I don't have information about that."


def is_relevant(
    results: list[RetrievedChunk], *, threshold: float = config.RELEVANCE_THRESHOLD
) -> bool:
    """True if the top result clears the threshold (cosine similarity, higher-is-better)."""
    if not results:
        return False
    return results[0].similarity >= threshold
