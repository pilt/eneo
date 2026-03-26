"""Unit tests for the echo completion model adapter."""

from uuid import uuid4

import pytest

from intric.ai_models.completion_models.completion_model import (
    Completion,
    CompletionModel,
    Context,
    ResponseType,
)
from intric.completion_models.infrastructure.adapters.echo_adapter import EchoAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def echo_model() -> CompletionModel:
    return CompletionModel(
        id=uuid4(),
        name="echo",
        nickname="Echo",
        family=None,
        max_input_tokens=4096,
        max_output_tokens=4096,
        is_deprecated=False,
        vision=False,
        reasoning=False,
    )


@pytest.fixture
def adapter(echo_model: CompletionModel) -> EchoAdapter:
    return EchoAdapter(model=echo_model)


def make_context(text: str) -> Context:
    return Context(input=text)


# ---------------------------------------------------------------------------
# Token limit
# ---------------------------------------------------------------------------


def test_token_limit_matches_model(adapter: EchoAdapter, echo_model: CompletionModel):
    assert adapter.get_token_limit_of_model() == echo_model.max_input_tokens


# ---------------------------------------------------------------------------
# Non-streaming response
# ---------------------------------------------------------------------------


async def test_get_response_echoes_input(adapter: EchoAdapter):
    ctx = make_context("Hello world")
    result = await adapter.get_response(ctx)

    assert isinstance(result, Completion)
    assert result.text == "Echo: Hello world"
    assert result.response_type == ResponseType.TEXT
    assert result.stop is True


async def test_get_response_includes_token_usage(adapter: EchoAdapter):
    ctx = make_context("one two three")
    result = await adapter.get_response(ctx)

    assert result.usage is not None
    assert result.usage.prompt_tokens > 0
    assert result.usage.completion_tokens > 0


async def test_get_response_empty_input(adapter: EchoAdapter):
    ctx = make_context("")
    result = await adapter.get_response(ctx)
    assert result.text == "Echo: "
    assert result.stop is True


# ---------------------------------------------------------------------------
# Phase 1: prepare_streaming
# ---------------------------------------------------------------------------


async def test_prepare_streaming_returns_input(adapter: EchoAdapter):
    ctx = make_context("stream me")
    stream = await adapter.prepare_streaming(ctx)
    assert stream == "stream me"


# ---------------------------------------------------------------------------
# Phase 2: iterate_stream
# ---------------------------------------------------------------------------


async def test_iterate_stream_yields_text_chunks(adapter: EchoAdapter):
    chunks = []
    async for chunk in adapter.iterate_stream(stream="hi there"):
        chunks.append(chunk)

    text_chunks = [c for c in chunks if c.text and not c.stop]
    assert len(text_chunks) > 0

    # All non-stop chunks have TEXT response type
    for chunk in text_chunks:
        assert chunk.response_type == ResponseType.TEXT


async def test_iterate_stream_reassembles_to_echo(adapter: EchoAdapter):
    chunks = []
    async for chunk in adapter.iterate_stream(stream="hello eneo"):
        chunks.append(chunk)

    full_text = "".join(c.text for c in chunks if c.text)
    assert full_text == "Echo: hello eneo"


async def test_iterate_stream_ends_with_stop_chunk(adapter: EchoAdapter):
    chunks = []
    async for chunk in adapter.iterate_stream(stream="test"):
        chunks.append(chunk)

    assert chunks, "no chunks yielded"
    last = chunks[-1]
    assert last.stop is True


async def test_iterate_stream_stop_chunk_has_usage(adapter: EchoAdapter):
    chunks = []
    async for chunk in adapter.iterate_stream(stream="usage test"):
        chunks.append(chunk)

    stop_chunk = next(c for c in chunks if c.stop)
    assert stop_chunk.usage is not None
    assert stop_chunk.usage.completion_tokens > 0


async def test_iterate_stream_word_count_matches(adapter: EchoAdapter):
    """Each word produces exactly one chunk (plus a stop chunk)."""
    input_text = "one two three"
    chunks = [c async for c in adapter.iterate_stream(stream=input_text)]

    reply_words = f"Echo: {input_text}".split(" ")
    non_stop = [c for c in chunks if not c.stop]
    assert len(non_stop) == len(reply_words)


# ---------------------------------------------------------------------------
# Two-phase round-trip (prepare → iterate)
# ---------------------------------------------------------------------------


async def test_two_phase_streaming_round_trip(adapter: EchoAdapter):
    ctx = make_context("round trip test")
    stream = await adapter.prepare_streaming(ctx)

    text = ""
    async for chunk in adapter.iterate_stream(stream=stream):
        if chunk.text:
            text += chunk.text

    assert text == "Echo: round trip test"
