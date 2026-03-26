"""
Vercel AI SDK gateway router.

Exposes POST /api/ai-gateway/chat — a streaming endpoint that implements the
Vercel AI SDK v5 UI Message Stream Protocol.  This allows any frontend using
the Vercel AI SDK `useChat` hook (or a compatible client) to connect to eneo
assistants directly.

The endpoint:
- Authenticates via the same mechanisms as the rest of the API (Bearer token
  or X-API-KEY header)
- Extracts the user's question from the last user message in `messages`
- Delegates to eneo's ConversationService (the same service used by the
  regular /conversations/ endpoint)
- Translates eneo's Completion stream into the Vercel AI SDK chunk format
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, AsyncIterable, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import Field

from intric.ai_gateway.protocol import (
    STREAM_DONE,
    RegenerateMessageRequest,
    SubmitMessageRequest,
    chunk_data,
    chunk_error,
    chunk_finish,
    chunk_finish_step,
    chunk_start,
    chunk_start_step,
    chunk_text_delta,
    chunk_text_end,
    chunk_text_start,
)
from intric.ai_models.completion_models.completion_model import ResponseType
from intric.database.database import AsyncSession, get_session_with_transaction
from intric.database.transaction import gen_transaction
from intric.server.dependencies.container import get_container

if TYPE_CHECKING:
    from intric.assistants.api.assistant_models import AssistantResponse
    from intric.main.container.container import Container

router = APIRouter()

_ANNOTATED_CHAT_REQUEST = Annotated[
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


async def _translate_stream(
    response: AssistantResponse,
    db_session: AsyncSession,
) -> AsyncIterable[str]:
    """
    Wrap eneo's Completion async-generator in a Vercel AI SDK stream.

    The DB session must stay alive for the duration of the stream because
    the underlying LiteLLM adapter may do final DB writes (token usage etc.)
    after the last chunk.  gen_transaction keeps the SQLAlchemy transaction
    open across the full yield sequence.
    """
    message_id = str(uuid4())
    text_id = str(uuid4())

    @gen_transaction(db_session)
    async def _stream():
        yield chunk_start(message_id)
        yield chunk_start_step()

        # Emit the session_id as a typed data chunk so the client can persist
        # it and pass it back as session_id in the next request.
        yield chunk_data("session", {"session_id": str(response.session.id)})

        text_started = False

        async for completion in response.answer:
            if completion.response_type == ResponseType.TEXT:
                if not text_started:
                    yield chunk_text_start(text_id)
                    text_started = True
                if completion.text:
                    yield chunk_text_delta(text_id, completion.text)

            elif completion.response_type == ResponseType.ERROR:
                yield chunk_error(completion.error or "Unknown error")
                return

            # TOOL_CALL, FILES, INTRIC_EVENT — ignored for now; the Vercel AI
            # SDK tool protocol can be added here incrementally.

        if text_started:
            yield chunk_text_end(text_id)

        yield chunk_finish_step()
        yield chunk_finish("stop")
        yield STREAM_DONE

    async for chunk in _stream():
        yield chunk


@router.post("/chat")
async def ai_gateway_chat(
    request: _ANNOTATED_CHAT_REQUEST,
    version: int = Query(default=1, ge=1, le=2),
    container: Container = Depends(get_container(with_user=True)),
    db_session: AsyncSession = Depends(get_session_with_transaction),
):
    """
    Vercel AI SDK UI Message Stream endpoint.

    Accepts the AI SDK v5 chat request body and streams back SSE events
    following the UI Message Stream Protocol.

    **Authentication**: same as the rest of the API — pass a Bearer token or
    `X-API-KEY` header.

    **Request body** (discriminated by `trigger`):
    - `submit-message` — send a new user message
    - `regenerate-message` — regenerate the last assistant turn

    **eneo-specific fields** (set via `useChat`'s `body` option):
    - `assistant_id` — UUID of the assistant to talk to (new conversations)
    - `session_id` — UUID of an existing session to continue

    One of `assistant_id` or `session_id` is required.

    **Response** — `text/event-stream` with header
    `x-vercel-ai-ui-message-stream: v1`.

    A `data-session` chunk is emitted early in the stream containing the
    eneo session UUID so clients can store it for conversation continuity:
    ```json
    {"type":"data-session","data":{"session_id":"<uuid>"}}
    ```
    """
    if request.assistant_id is None and request.session_id is None:
        raise HTTPException(
            status_code=422,
            detail="Either assistant_id or session_id must be provided.",
        )

    # Extract the question from the last user message in the messages list
    last_user = next(
        (m for m in reversed(request.messages) if m.role == "user"),
        None,
    )
    if last_user is None:
        raise HTTPException(status_code=422, detail="No user message found in messages.")

    question = last_user.text_content()
    if not question:
        raise HTTPException(status_code=422, detail="User message has no text content.")

    conversation_service = container.conversation_service()

    response = await conversation_service.ask_conversation(
        question=question,
        session_id=request.session_id,
        assistant_id=request.assistant_id,
        stream=True,
        version=version,
    )

    return StreamingResponse(
        _translate_stream(response, db_session),
        media_type="text/event-stream",
        headers=_STREAM_HEADERS,
    )
