"""FastAPI contract tests for POST /v1/ask (M2.4-01, M2.4-02) — pipeline faked, no network."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

import config
import query.api as api
from query import pipeline
from query.api import app
from query.retrieval import RetrievedChunk

client = TestClient(app)

_Pipeline = Callable[[str], tuple[list[RetrievedChunk] | None, Iterator[str]]]


def _fake(sources: list[RetrievedChunk] | None, tokens: list[str]) -> _Pipeline:
    def _run(_question: str) -> tuple[list[RetrievedChunk] | None, Iterator[str]]:
        return sources, iter(tokens)

    return _run


_SOURCE = RetrievedChunk("alpha text", 0.9, "A", "p1", 0, None, None)


@pytest.fixture(autouse=True)
def _reset_limiter() -> Iterator[None]:
    api._hits.clear()
    yield
    api._hits.clear()


def test_empty_question_returns_400() -> None:
    assert client.post("/v1/ask", json={"question": "   "}).status_code == 400


def test_overlong_question_returns_400() -> None:
    assert client.post("/v1/ask", json={"question": "x" * 501}).status_code == 400


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_cors_allows_both_dev_loopback_spellings(
    monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    # A browser on 127.0.0.1:3000 sends a *different* Origin than localhost:3000 — both must pass,
    # or local widget testing hits a silent CORS wall (the M2.4 CORS trap).
    monkeypatch.setattr(pipeline, "run_pipeline", _fake([_SOURCE], ["hi"]))
    r = client.post("/v1/ask", json={"question": "hi"}, headers={"Origin": origin})
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_blocks_unknown_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "run_pipeline", _fake(None, ["x"]))
    r = client.post("/v1/ask", json={"question": "hi"}, headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in r.headers


def test_sse_event_ordering_sources_delta_done(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "run_pipeline", _fake([_SOURCE], ["Nic ", "works."]))
    r = client.post("/v1/ask", json={"question": "q"})
    body = r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    assert body.index("event: sources") < body.index("event: delta") < body.index("event: done")
    assert '"title": "A"' in body
    assert body.count("event: delta") == 2  # one delta per token
    assert "Nic " in body and "works." in body


def test_gate_decline_sends_no_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    decline = "Sorry, I don't have information about that."
    monkeypatch.setattr(pipeline, "run_pipeline", _fake(None, [decline]))
    body = client.post("/v1/ask", json={"question": "weather?"}).text
    assert "event: sources" not in body
    assert "event: delta" in body and "event: done" in body
    assert decline in body


def test_prompt_side_decline_sends_no_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    # Gate passed (sources retrieved) but the model streamed the canned decline — drop the sources.
    decline = "Sorry, I don't have information about that."
    monkeypatch.setattr(pipeline, "run_pipeline", _fake([_SOURCE], [decline]))
    body = client.post("/v1/ask", json={"question": "weather?"}).text
    assert "event: sources" not in body
    assert "event: delta" in body and "event: done" in body
    assert decline in body


def test_rate_limit_returns_429_before_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "run_pipeline", _fake(None, ["x"]))
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 1)
    first = client.post("/v1/ask", json={"question": "a"})
    second = client.post("/v1/ask", json={"question": "b"})
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {"error": "rate_limited"}
