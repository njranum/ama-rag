"""Shared runtime config for the RAG backend.

Loads `.env` (stdlib, no dependency) and records the **locked embedding model + dimension**
(M0.5-01) — the seam shared by Layer 1 (ingestion) and Layer 2 (query). This module is the
single source of truth for that lock; both pipelines import it so they cannot drift apart.
"""

from __future__ import annotations

import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env(path: Path = _ENV_PATH) -> None:
    """Minimal `.env` loader: `KEY=VALUE` lines into os.environ; never overrides existing."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

# --- Locked embedding model (M0.5-01) — the L1<->L2 seam --------------------------------
# Hosted on Pinecone Inference. Chunks embed as input_type="passage", queries as "query".
# TRAP: llama-text-embed-v2 defaults to 1024 dims — 384 requires passing `dimension` on the
# embed call AND creating the Pinecone index at 384. A mismatch is silent (working-but-wrong).
EMBED_MODEL: str = "llama-text-embed-v2"
EMBED_DIM: int = 384
EMBED_METRIC: str = "cosine"

# --- Pinecone index (M1.2-01) — production vector store at the locked dimension ---------
PINECONE_INDEX: str = "portfolio-rag"
PINECONE_CLOUD: str = "aws"
PINECONE_REGION: str = "us-east-1"  # Pinecone Starter free-tier constraint

# --- Local vector store (Chroma, Phase-1 dev) ------------------------------------------
CHROMA_PATH: str = ".chroma"
CHROMA_COLLECTION: str = "portfolio"

# --- Query pipeline (Layer 2) ----------------------------------------------------------
TOP_K: int = 4  # retrieved chunks per query (tunable knob)
# Relevance-gate threshold (cosine similarity, higher-is-better). Calibrated in M2.2-02 against the
# Phase-1 eval set: sits just below the lowest should-answer score (0.413), rejecting all 15
# should-refuse (highest 0.402) — a clean but narrow gap. PROVISIONAL (synthetic corpus); re-locked
# on real content at M4.2-03. Re-derive with `python -m query.calibrate`.
RELEVANCE_THRESHOLD: float = 0.403

# --- Generation (Layer 2, Stage 4) — Claude Haiku 4.5 via the Anthropic Messages API ---
GEN_MODEL: str = "claude-haiku-4-5"  # bare alias; grounded extractive QA — smallest model is plenty
GEN_TEMPERATURE: float = 0.2  # low — faithful, grounded; reduces drift/hallucination
GEN_MAX_TOKENS: int = 400  # caps answer length, cost, latency
GEN_TIMEOUT_S: float = 20.0  # request timeout; on any error we surface a graceful fallback

# --- Secrets / ids (from .env; server-side only) ---------------------------------------
PINECONE_API_KEY: str | None = os.environ.get("PINECONE_API_KEY")
ANTHROPIC_API_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")
NOTION_TOKEN: str | None = os.environ.get("NOTION_TOKEN")
PORTFOLIO_PARENT_PAGE_ID: str | None = os.environ.get("PORTFOLIO_PARENT_PAGE_ID")
