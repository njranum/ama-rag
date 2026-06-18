"""Layer 1, Stage 3 — embed chunks (Pinecone Inference) and store to local Chroma.

Embeds each chunk with `input_type="passage"` at the locked 384 dimension, then upserts the
vector + chunk text + metadata into a local Chroma collection (Phase-1 dev store). Production
swaps to Pinecone integrated inference (M4.2-01). The collection uses **cosine** space so its
distance matches the cosine-similarity convention Layer 2 normalises to. See docs/L1_Ingestion.md
(Vector store + score normalisation).

Run from the repo root:  python -m ingest.embed_store
"""

from __future__ import annotations

import sys
from typing import Any

import chromadb
from pinecone import Pinecone

import config
from ingest.chunker import Chunk, chunk_pages

_EMBED_BATCH = 96  # Pinecone Inference max inputs per embed call


def _vector(embedding: Any) -> list[float]:
    values = getattr(embedding, "values", None)
    if values is None and isinstance(embedding, dict):
        values = embedding.get("values")
    if values is None:
        raise TypeError(f"could not read .values from embedding of type {type(embedding)!r}")
    return [float(x) for x in values]


def _chunk_id(chunk: Chunk) -> str:
    return f"{chunk.page_id}:{chunk.chunk_position}"


def _chunk_metadata(chunk: Chunk) -> dict[str, Any]:
    # url/anchor (M1.7-01) are nullable; stored as "" because Chroma drops None-valued keys
    # entirely (verified), which would violate "chunks carry the keys". Layer 2 reads "" as null.
    return {
        "page_id": chunk.page_id,
        "title": chunk.title,
        "last_edited_time": chunk.last_edited_time,
        "chunk_position": chunk.chunk_position,
        "url": chunk.url or "",
        "anchor": chunk.anchor or "",
    }


def embed_chunks(chunks: list[Chunk], *, client: Any = None) -> list[list[float]]:
    """Embed chunk texts via Pinecone Inference (input_type=passage), batched."""
    pc: Any = client or Pinecone(api_key=config.PINECONE_API_KEY)
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), _EMBED_BATCH):
        batch = chunks[start : start + _EMBED_BATCH]
        resp = pc.inference.embed(
            model=config.EMBED_MODEL,
            inputs=[c.text for c in batch],
            parameters={"input_type": "passage", "dimension": config.EMBED_DIM},
        )
        vectors.extend(_vector(emb) for emb in resp)
    return vectors


def get_collection(*, path: str | None = None, name: str | None = None) -> Any:
    """Open (or create) the local Chroma collection, configured for cosine distance."""
    client = chromadb.PersistentClient(path=path or config.CHROMA_PATH)
    return client.get_or_create_collection(
        name=name or config.CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def store_chunks(chunks: list[Chunk], vectors: list[list[float]], *, collection: Any = None) -> int:
    """Upsert chunks + their vectors + metadata into Chroma. Returns the number stored."""
    if not chunks:
        return 0
    col: Any = collection if collection is not None else get_collection()
    col.upsert(
        ids=[_chunk_id(c) for c in chunks],
        embeddings=vectors,
        documents=[c.text for c in chunks],
        metadatas=[_chunk_metadata(c) for c in chunks],
    )
    return len(chunks)


def stored_page_state(collection: Any) -> dict[str, str]:
    """Map page_id -> last_edited_time from stored chunk metadata (its own sync state)."""
    got = collection.get(include=["metadatas"])
    state: dict[str, str] = {}
    for md in got["metadatas"]:
        state[md["page_id"]] = md["last_edited_time"]
    return state


def delete_page(collection: Any, page_id: str) -> None:
    """Delete every chunk belonging to a page id."""
    collection.delete(where={"page_id": page_id})


def _embed_query(pc: Any, question: str) -> list[float]:
    resp = pc.inference.embed(
        model=config.EMBED_MODEL,
        inputs=[question],
        parameters={"input_type": "query", "dimension": config.EMBED_DIM},
    )
    return _vector(resp[0])


def main() -> int:
    from ingest.notion_fetch import fetch_portfolio_pages

    try:
        records = fetch_portfolio_pages()
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    chunks = chunk_pages(records)
    pc: Any = Pinecone(api_key=config.PINECONE_API_KEY)
    vectors = embed_chunks(chunks, client=pc)

    bad = [i for i, v in enumerate(vectors) if len(v) != config.EMBED_DIM]
    if bad:
        print(f"FAIL: {len(bad)} vector(s) not {config.EMBED_DIM}-dim", file=sys.stderr)
        return 1

    col = get_collection()
    n = store_chunks(chunks, vectors, collection=col)
    print(
        f"Stored {n} chunks -> Chroma {config.CHROMA_COLLECTION!r} "
        f"at {config.CHROMA_PATH!r} (count={col.count()})\n"
    )

    # Sanity similarity query (input_type=query) — proves neighbours are sensible.
    # The real query pipeline is M2.1; this only satisfies the M1.5 Verify.
    question = "What experience does the candidate have with AWS and cloud infrastructure?"
    res = col.query(query_embeddings=[_embed_query(pc, question)], n_results=3)
    print(f"sanity query: {question}")
    for md, dist in zip(res["metadatas"][0], res["distances"][0], strict=True):
        print(f"  - {md['title']:<48} cos_sim={1 - dist:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
