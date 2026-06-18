"""M0.5-01 — Lock the embedding model + dimension (live verification).

Confirms the locked hosted model is in the Pinecone Inference catalogue, then embeds a
sample chunk at `dimension=384` / `input_type="passage"` and asserts the returned vector
length is 384 (not the 1024 default). The lock itself lives in `config.py`; this proves it
holds against the live API.

Run from the repo root:  python -m scripts.lock_embedding
"""

from __future__ import annotations

import sys
from typing import Any

from pinecone import Pinecone

import config


def _extract_vector(embedding: Any) -> list[float]:
    """Pull the float vector out of a Pinecone embedding (attr or mapping access)."""
    values = getattr(embedding, "values", None)
    if values is None and isinstance(embedding, dict):
        values = embedding.get("values")
    if values is None:
        raise TypeError(f"could not read .values from embedding of type {type(embedding)!r}")
    return [float(x) for x in values]


def _model_names(models: Any) -> list[str]:
    names: list[str] = []
    for m in models:
        name = getattr(m, "model", None) or getattr(m, "name", None)
        if name is None and isinstance(m, dict):
            name = m.get("model") or m.get("name")
        if name:
            names.append(str(name))
    return names


def main() -> int:
    if not config.PINECONE_API_KEY:
        print("PINECONE_API_KEY not set — check .env.", file=sys.stderr)
        return 1

    pc = Pinecone(api_key=config.PINECONE_API_KEY)
    print(
        f"Lock under test: model={config.EMBED_MODEL}  "
        f"dim={config.EMBED_DIM}  metric={config.EMBED_METRIC}\n"
    )

    # 1) Live catalogue — is the model still hosted?
    names = _model_names(pc.inference.list_models())
    print("Hosted inference models:", ", ".join(names) if names else "(could not parse)")
    if names and config.EMBED_MODEL not in names:
        print(f"WARNING: {config.EMBED_MODEL!r} not in live catalogue.", file=sys.stderr)

    # 2) Test embed at the locked dim / passage encoding.
    resp = pc.inference.embed(
        model=config.EMBED_MODEL,
        inputs=["A short sample portfolio chunk about Nic's experience with AWS and Python."],
        parameters={"input_type": "passage", "dimension": config.EMBED_DIM},
    )
    vec = _extract_vector(resp[0])
    print(f"\nTest embed (input_type=passage): returned vector length = {len(vec)}")

    if len(vec) != config.EMBED_DIM:
        print(
            f"FAIL: expected {config.EMBED_DIM}, got {len(vec)} — the 1024-default trap.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: vector length is {config.EMBED_DIM}. Lock holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
