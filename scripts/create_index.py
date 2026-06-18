"""M1.2-01 — Create the production Pinecone index at the locked dimension.

Idempotent: creates a serverless index (`aws`/`us-east-1`) at `dimension=384`, `metric=cosine`
if it doesn't already exist, then verifies — confirms the index dimension/metric and embeds a
test string asserting the vector is 384-dim (the seam the index must match). Safe to re-run.

Run from the repo root:  python -m scripts.create_index
"""

from __future__ import annotations

import sys
from typing import Any

from pinecone import Pinecone, ServerlessSpec

import config


def _extract_vector(embedding: Any) -> list[float]:
    values = getattr(embedding, "values", None)
    if values is None and isinstance(embedding, dict):
        values = embedding.get("values")
    if values is None:
        raise TypeError(f"could not read .values from embedding of type {type(embedding)!r}")
    return [float(x) for x in values]


def main() -> int:
    if not config.PINECONE_API_KEY:
        print("PINECONE_API_KEY not set — check .env.", file=sys.stderr)
        return 1

    pc = Pinecone(api_key=config.PINECONE_API_KEY)
    name = config.PINECONE_INDEX

    if pc.has_index(name):
        print(f"Index {name!r} already exists — skipping creation (idempotent).")
    else:
        print(
            f"Creating index {name!r}: dim={config.EMBED_DIM}, metric={config.EMBED_METRIC}, "
            f"{config.PINECONE_CLOUD}/{config.PINECONE_REGION} ..."
        )
        pc.create_index(
            name=name,
            dimension=config.EMBED_DIM,
            metric=config.EMBED_METRIC,
            spec=ServerlessSpec(cloud=config.PINECONE_CLOUD, region=config.PINECONE_REGION),
        )
        print("Created.")

    ok = True

    # Verify the index config matches the lock.
    desc = pc.describe_index(name)
    idx_dim = getattr(desc, "dimension", None)
    idx_metric = str(getattr(desc, "metric", "")).lower()
    print(f"describe_index: dimension={idx_dim}, metric={idx_metric}")
    if idx_dim != config.EMBED_DIM:
        print(f"FAIL: index dimension {idx_dim} != {config.EMBED_DIM}", file=sys.stderr)
        ok = False
    if config.EMBED_METRIC not in idx_metric:
        print(f"FAIL: index metric {idx_metric!r} != {config.EMBED_METRIC!r}", file=sys.stderr)
        ok = False

    # Verify an embed lands at 384 — the dimension the index must match.
    resp = pc.inference.embed(
        model=config.EMBED_MODEL,
        inputs=["A short sample portfolio chunk about Nic's experience with AWS."],
        parameters={"input_type": "passage", "dimension": config.EMBED_DIM},
    )
    vec = _extract_vector(resp[0])
    print(f"test embed length = {len(vec)}")
    if len(vec) != config.EMBED_DIM:
        print(f"FAIL: embed length {len(vec)} != {config.EMBED_DIM}", file=sys.stderr)
        ok = False

    if not ok:
        return 1
    print(f"OK: index {name!r} ready at {config.EMBED_DIM}/{config.EMBED_METRIC}; embeds match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
