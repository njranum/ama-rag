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

# --- Vector store backend selection (M4.2-01) -----------------------------------------
# Selects only the STORE, not the embedding: "chroma" = local Chroma (Phase-1/2 dev),
# "pinecone" = hosted Pinecone index (Phase-3 prod). Embeddings are Pinecone Inference either way
# (EMBED_MODEL above). Scores are normalised to cosine similarity (higher=better) in both, so the
# RELEVANCE_THRESHOLD travels unchanged across the swap. Prod sets VECTOR_STORE=pinecone in .env.
VECTOR_STORE: str = os.environ.get("VECTOR_STORE", "chroma").strip().lower()

# --- Query pipeline (Layer 2) ----------------------------------------------------------
TOP_K: int = 4  # retrieved chunks per query (tunable knob)
# Relevance-gate threshold (cosine similarity, higher-is-better). LOCKED on the real corpus at
# M4.2-03: sits just below the lowest should-answer score (0.385, "what is pomobar?"). Catches all
# off-topic + both injection attempts (highest such ≈ 0.24). No clean gap — three *unanswerable-
# about-Nic* questions ("car", "political views", "star sign", 0.44–0.48) retrieve his pages and
# clear the gate; by design the prompt-side decline (M2.3-01) backstops that weak-but-cleared
# middle rather than hard-rejecting genuine questions. Supersedes the provisional synthetic 0.403.
# Re-derive with `python -m query.calibrate`.
RELEVANCE_THRESHOLD: float = 0.375

# --- Generation (Layer 2, Stage 4) — Claude Haiku 4.5 via the Anthropic Messages API ---
GEN_MODEL: str = "claude-haiku-4-5"  # bare alias; grounded extractive QA — smallest model is plenty
GEN_TEMPERATURE: float = 0.2  # low — faithful, grounded; reduces drift/hallucination
GEN_MAX_TOKENS: int = 400  # caps answer length, cost, latency
GEN_TIMEOUT_S: float = 20.0  # request timeout; on any error we surface a graceful fallback

# --- Serving / API (Layer 2 — M2.4: FastAPI POST /v1/ask) ------------------------------
MAX_QUESTION_CHARS: int = 500  # cap doubles as a cheap abuse/cost guard
RATE_LIMIT_PER_MIN: int = 30  # app-level backstop; edge limits tuned at M4.1 (Cloudflare)
# CORS allowlist: local dev origin always; production site origin added once known (env).
# Dev origins: BOTH spellings of the loopback — a browser on http://127.0.0.1:3000 sends that as
# its Origin, which is a *different* origin to http://localhost:3000 as far as CORS is concerned, so
# listing only one blocks local testing on the other with a silent CORS wall (the M2.4 CORS trap).
CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"] + (
    [os.environ["PROD_SITE_ORIGIN"]] if os.environ.get("PROD_SITE_ORIGIN") else []
)

# --- Secrets / ids (from .env; server-side only) ---------------------------------------
PINECONE_API_KEY: str | None = os.environ.get("PINECONE_API_KEY")
ANTHROPIC_API_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")
NOTION_TOKEN: str | None = os.environ.get("NOTION_TOKEN")
PORTFOLIO_PARENT_PAGE_ID: str | None = os.environ.get("PORTFOLIO_PARENT_PAGE_ID")
