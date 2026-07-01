"""Layer 2 serving — FastAPI `POST /v1/ask` with the SSE contract (M2.4-01, M2.4-02).

Stateless single-turn endpoint. Validates + caps the question (400), enforces a CORS allowlist and
an app-level rate limit (HTTP 429 *before* the stream opens), then streams Server-Sent Events:
`sources` (once, up front) -> `delta` (per token) -> `done`, with an `error` event on failure.
Any decline sends **no** `sources` event — the gate decline is sourceless up front, and a
prompt-side decline (gate passed, model still declined) has its sources dropped by peeking the
stream (see `pipeline.resolve_sources`); the canned decline streams as `delta` + `done` (one widget
code path for answer vs decline). See docs/L2_Query_Pipeline.md (API contract).

Run:  uvicorn query.api:app --reload --port 8000
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from collections.abc import Iterator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

import config
from query import pipeline
from query.generate import FALLBACK_MESSAGE
from query.retrieval import RetrievedChunk

app = FastAPI(title="RAG ask-me-anything API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["POST"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


# --- minimal in-memory fixed-window rate limiter (app-level backstop; edge limits = M4.1) ---
_hits: defaultdict[str, list[float]] = defaultdict(list)


def _rate_limited(client_ip: str) -> bool:
    now = time.monotonic()
    recent = [t for t in _hits[client_ip] if now - t < 60.0]
    recent.append(now)
    _hits[client_ip] = recent
    return len(recent) > config.RATE_LIMIT_PER_MIN


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _source_payload(chunk: RetrievedChunk) -> dict[str, object]:
    return {"title": chunk.title, "text": chunk.text, "url": chunk.url, "anchor": chunk.anchor}


def _event_stream(question: str) -> Iterator[str]:
    try:
        sources, tokens = pipeline.run_pipeline(question)
        # A prompt-side decline (gate passed, model still declined) shows no sources either — peek
        # the stream and drop them so it matches the gate-decline path from the widget's view.
        sources, tokens = pipeline.resolve_sources(sources, tokens)
        if sources is not None:
            yield _sse("sources", {"sources": [_source_payload(c) for c in sources]})
        for token in tokens:
            yield _sse("delta", {"text": token})
        yield _sse("done", {})
    except Exception as exc:  # never surface a raw trace to the widget
        print(f"ask stream failed: {exc}", file=sys.stderr)
        yield _sse("error", {"message": FALLBACK_MESSAGE})


@app.post("/v1/ask")
def ask(req: AskRequest, request: Request) -> Response:
    client_ip = request.client.host if request.client else "unknown"
    if _rate_limited(client_ip):
        return JSONResponse({"error": "rate_limited"}, status_code=429)

    question = req.question.strip()
    if not question or len(question) > config.MAX_QUESTION_CHARS:
        return JSONResponse({"error": "invalid_question"}, status_code=400)

    return StreamingResponse(_event_stream(question), media_type="text/event-stream")
