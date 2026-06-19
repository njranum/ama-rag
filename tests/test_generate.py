"""Network-free tests for generation (M2.3-02): streaming passthrough + graceful fallback."""

from __future__ import annotations

from typing import Any

from query.generate import FALLBACK_MESSAGE, stream_answer
from query.retrieval import RetrievedChunk


class _StubStream:
    def __init__(self, texts: list[str], raise_exc: Exception | None) -> None:
        self._texts = texts
        self._raise = raise_exc

    def __enter__(self) -> _StubStream:
        if self._raise is not None:
            raise self._raise
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    @property
    def text_stream(self) -> Any:
        return iter(self._texts)


class _StubMessages:
    def __init__(self, texts: list[str], raise_exc: Exception | None) -> None:
        self._texts = texts
        self._raise = raise_exc

    def stream(self, **_: Any) -> _StubStream:
        return _StubStream(self._texts, self._raise)


class _StubClient:
    def __init__(self, texts: list[str] | None = None, raise_exc: Exception | None = None) -> None:
        self.messages = _StubMessages(texts or [], raise_exc)


_CHUNKS = [RetrievedChunk("alpha", 0.5, "A", "p", 0, None, None)]


def test_tokens_stream_through() -> None:
    client = _StubClient(texts=["Nic ", "worked ", "at Orrery."])
    out = "".join(stream_answer("Where does Nic work?", _CHUNKS, client=client))
    assert out == "Nic worked at Orrery."


def test_error_before_any_token_yields_only_fallback() -> None:
    client = _StubClient(raise_exc=RuntimeError("api down"))
    out = list(stream_answer("Q", _CHUNKS, client=client))
    assert out == [FALLBACK_MESSAGE]  # graceful fallback, no traceback
