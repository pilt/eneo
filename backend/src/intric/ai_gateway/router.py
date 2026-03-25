"""
Vercel AI SDK gateway router.

Exposes POST /api/ai-gateway/chat — a streaming endpoint that implements the
Vercel AI SDK UI Message Stream Protocol (v5).  This allows any frontend using
the Vercel AI SDK `useChat` hook (or a compatible client) to connect directly
to eneo.

Currently wired to the echo adapter for testing.  Swap `echo_stream` for a
real LiteLLM-backed adapter to connect to actual models.
"""

from __future__ import annotations

from typing import Annotated, Union

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import Field

from intric.ai_gateway.echo_adapter import echo_stream
from intric.ai_gateway.protocol import (
    RegenerateMessageRequest,
    SubmitMessageRequest,
)

router = APIRouter()

ChatRequest = Annotated[
    Union[SubmitMessageRequest, RegenerateMessageRequest],
    Field(discriminator="trigger"),
]

_STREAM_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    "x-accel-buffering": "no",
}


@router.post("/chat")
async def ai_gateway_chat(request: ChatRequest):
    """
    Vercel AI SDK UI Message Stream endpoint.

    Accepts the AI SDK v5 chat request body and streams back SSE events
    following the UI Message Stream Protocol.

    **Request body** (discriminated by `trigger`):
    - `submit-message` — send a new user message
    - `regenerate-message` — regenerate the last assistant turn

    **Response** — `text/event-stream` with header
    `x-vercel-ai-ui-message-stream: v1`.
    """
    return StreamingResponse(
        echo_stream(request.messages),
        media_type="text/event-stream",
        headers=_STREAM_HEADERS,
    )
