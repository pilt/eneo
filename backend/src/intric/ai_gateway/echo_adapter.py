"""
Echo adapter — a fake AI provider that echoes back the last user message.
Useful for testing the Vercel AI SDK gateway protocol end-to-end.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator
from uuid import uuid4

from intric.ai_gateway.protocol import (
    UIMessage,
    chunk_finish,
    chunk_finish_step,
    chunk_start,
    chunk_start_step,
    chunk_text_delta,
    chunk_text_end,
    chunk_text_start,
    STREAM_DONE,
)


async def echo_stream(messages: list[UIMessage]) -> AsyncIterator[str]:
    """
    Yields SSE chunks that echo back the last user message, word by word.
    Simulates a streaming AI response.
    """
    # Find the last user message
    last_user = next(
        (m for m in reversed(messages) if m.role == "user"),
        None,
    )
    text = last_user.text_content() if last_user else "(no message)"
    reply = f"Echo: {text}"

    message_id = str(uuid4())
    text_id = str(uuid4())

    yield chunk_start(message_id)
    yield chunk_start_step()
    yield chunk_text_start(text_id)

    # Stream word by word with a small delay to simulate generation
    words = reply.split(" ")
    for i, word in enumerate(words):
        delta = word if i == 0 else f" {word}"
        yield chunk_text_delta(text_id, delta)
        await asyncio.sleep(0.05)

    yield chunk_text_end(text_id)
    yield chunk_finish_step()
    yield chunk_finish("stop")
    yield STREAM_DONE
