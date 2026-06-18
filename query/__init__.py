"""Layer 2 — Query pipeline & serving.

Embed query -> top-k retrieval -> relevance gate -> grounded prompt ->
Claude Haiku 4.5 (streamed) -> FastAPI `POST /v1/ask` (SSE).

See docs/L2_Query_Pipeline.md for the full design and decisions log.
"""
