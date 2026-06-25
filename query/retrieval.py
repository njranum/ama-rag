"""Layer 2, Stages 1-2 — embed the query and retrieve top-k chunks from the vector store.

Embeds the question with `input_type="query"` (same model/dimension as Layer 1 — the seam), runs a
cosine top-k search against local Chroma, and returns results with scores normalised to **cosine
similarity, higher-is-better** (Chroma returns a distance ≈ 1 − cosine). That normalisation is what
lets one threshold value travel unchanged from local Chroma to prod Pinecone. See
docs/L2_Query_Pipeline.md (retrieval + score normalisation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pinecone import Pinecone

import config
from ingest.embed_store import get_collection, get_index


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    similarity: float
    title: str
    page_id: str
    chunk_position: int
    url: str | None
    anchor: str | None


def _vector(embedding: Any) -> list[float]:
    values = getattr(embedding, "values", None)
    if values is None and isinstance(embedding, dict):
        values = embedding.get("values")
    if values is None:
        raise TypeError(f"could not read .values from embedding of type {type(embedding)!r}")
    return [float(x) for x in values]


def embed_query(question: str, *, client: Any = None) -> list[float]:
    """Embed a query with input_type='query' — mirrors Layer 1's passage embedding (the seam)."""
    pc: Any = client or Pinecone(api_key=config.PINECONE_API_KEY)
    resp = pc.inference.embed(
        model=config.EMBED_MODEL,
        inputs=[question],
        parameters={"input_type": "query", "dimension": config.EMBED_DIM},
    )
    return _vector(resp[0])


def _none_if_empty(value: Any) -> str | None:
    # Chroma stores nullable url/anchor as "" (it drops None-valued keys); read "" back as None.
    return value or None


def retrieve(
    question: str,
    *,
    k: int = config.TOP_K,
    collection: Any = None,
    index: Any = None,
    client: Any = None,
) -> list[RetrievedChunk]:
    """Embed the question; return top-k chunks as cosine similarity (higher=better).

    Routes to the configured store (config.VECTOR_STORE): local Chroma (dev) or the hosted Pinecone
    index (prod). Both normalise to cosine similarity, so the relevance gate is store-agnostic and
    the calibrated threshold travels unchanged across the swap (M4.2-01).
    """
    if config.VECTOR_STORE == "pinecone":
        return _retrieve_pinecone(question, k=k, index=index, client=client)
    return _retrieve_chroma(question, k=k, collection=collection, client=client)


def _retrieve_chroma(
    question: str, *, k: int, collection: Any, client: Any
) -> list[RetrievedChunk]:
    col: Any = collection if collection is not None else get_collection()
    qvec = embed_query(question, client=client)
    res = col.query(
        query_embeddings=[qvec],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]

    results: list[RetrievedChunk] = []
    for doc, md, dist in zip(docs, metas, dists, strict=True):
        results.append(
            RetrievedChunk(
                text=doc,
                similarity=1.0 - float(dist),  # Chroma cosine distance -> cosine similarity
                title=md["title"],
                page_id=md["page_id"],
                chunk_position=int(md["chunk_position"]),
                url=_none_if_empty(md.get("url")),
                anchor=_none_if_empty(md.get("anchor")),
            )
        )
    return results


def _retrieve_pinecone(question: str, *, k: int, index: Any, client: Any) -> list[RetrievedChunk]:
    idx: Any = index if index is not None else get_index()
    qvec = embed_query(question, client=client)
    res = idx.query(vector=qvec, top_k=k, include_metadata=True)
    matches = res["matches"] if isinstance(res, dict) else getattr(res, "matches", [])

    results: list[RetrievedChunk] = []
    for m in matches:
        md = m["metadata"] if isinstance(m, dict) else m.metadata
        score = m["score"] if isinstance(m, dict) else m.score
        results.append(
            RetrievedChunk(
                text=md["text"],  # Pinecone carries the chunk text in metadata
                similarity=float(score),  # Pinecone cosine metric returns similarity directly
                title=md["title"],
                page_id=md["page_id"],
                chunk_position=int(md["chunk_position"]),
                url=_none_if_empty(md.get("url")),
                anchor=_none_if_empty(md.get("anchor")),
            )
        )
    return results
