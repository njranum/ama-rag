"""Layer 1 — Offline ingestion.

Notion (Portfolio subtree) -> chunk (~500 tok / ~50 overlap) -> hosted Pinecone
Inference embedding (384-dim) -> vector store (Chroma local / Pinecone prod).

See docs/L1_Ingestion.md for the full design and decisions log.
"""
