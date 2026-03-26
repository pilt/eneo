"""
Vercel AI SDK gateway router.

Two endpoints:

POST /api/ai-gateway/chat
    **Data Stream Protocol** — the format used by the Vercel AI SDK
    ``useChat`` React hook (``streamProtocol: "data"``, the default).
    Response: ``text/plain`` with header ``x-vercel-ai-data-stream: v1``.

POST /api/ai-gateway/chat-ui
    **UI Message Stream Protocol** — named SSE events.
    Response: ``text/event-stream`` with header
    ``x-vercel-ai-ui-message-stream: v1``.
    Used by the CLI client and other tooling that consumes the newer format.

Both endpoints:
- Authenticate via the same mechanisms as the rest of the API (Bearer /
  X-API-KEY header)
- Extract the user question from the last ``role: "user"`` message
- Delegate to eneo's ConversationService
- Accept ``assistant_id`` or ``session_id`` via the request body
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterable, Union
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from intric.ai_gateway.protocol import (
    STREAM_DONE,
    DS_DONE_HEADER,
    DS_DONE_HEADER_VALUE,
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
    ds_data,
    ds_error,
    ds_finish,
    ds_finish_step,
    ds_text,
)
from intric.ai_models.completion_models.completion_model import ResponseType
from intric.database.database import AsyncSession, get_session_with_transaction
from intric.database.transaction import gen_transaction
from intric.server.dependencies.container import get_container

if TYPE_CHECKING:
    from intric.assistants.api.assistant_models import AssistantResponse
    from intric.main.container.container import Container

router = APIRouter()

# SubmitMessageRequest first — it's the common case and has trigger optional,
# so it will match any request that doesn't explicitly set trigger=regenerate-message.
ChatRequestBody = Union[SubmitMessageRequest, RegenerateMessageRequest]

_UI_STREAM_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    "x-accel-buffering": "no",
}

_DATA_STREAM_HEADERS = {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    DS_DONE_HEADER: DS_DONE_HEADER_VALUE,
    "x-accel-buffering": "no",
}


# ---------------------------------------------------------------------------
# Shared: extract question & call ConversationService
# ---------------------------------------------------------------------------


async def _call_conversation_service(
    request: ChatRequestBody,
    container: "Container",
    version: int,
) -> "AssistantResponse":
    if request.assistant_id is None and request.session_id is None:
        raise HTTPException(
            status_code=422,
            detail="Either assistant_id or session_id must be provided.",
        )

    last_user = next(
        (m for m in reversed(request.messages) if m.role == "user"),
        None,
    )
    if last_user is None:
        raise HTTPException(status_code=422, detail="No user message found in messages.")

    question = last_user.text_content()
    if not question:
        raise HTTPException(status_code=422, detail="User message has no text content.")

    return await container.conversation_service().ask_conversation(
        question=question,
        session_id=request.session_id,
        assistant_id=request.assistant_id,
        stream=True,
        version=version,
    )


# ---------------------------------------------------------------------------
# Data Stream translator  (useChat default)
# ---------------------------------------------------------------------------


async def _data_stream(
    response: "AssistantResponse",
    db_session: AsyncSession,
) -> AsyncIterable[str]:
    prompt_tokens = 0
    completion_tokens = 0

    @gen_transaction(db_session)
    async def _stream():
        nonlocal prompt_tokens, completion_tokens

        # Surface the eneo session_id as a typed data annotation so the
        # frontend can store it for conversation continuity.
        yield ds_data([{"session_id": str(response.session.id)}])

        async for completion in response.answer:
            if completion.response_type == ResponseType.TEXT:
                if completion.text:
                    yield ds_text(completion.text)
                if completion.usage:
                    prompt_tokens = completion.usage.prompt_tokens or 0
                    completion_tokens = completion.usage.completion_tokens or 0

            elif completion.response_type == ResponseType.ERROR:
                yield ds_error(completion.error or "Unknown error")
                return

        yield ds_finish_step("stop", prompt_tokens, completion_tokens)
        yield ds_finish("stop", prompt_tokens, completion_tokens)

    async for chunk in _stream():
        yield chunk


# ---------------------------------------------------------------------------
# UI Message Stream translator  (CLI client / newer tooling)
# ---------------------------------------------------------------------------


async def _ui_stream(
    response: "AssistantResponse",
    db_session: AsyncSession,
) -> AsyncIterable[str]:
    message_id = str(uuid4())
    text_id = str(uuid4())

    @gen_transaction(db_session)
    async def _stream():
        yield chunk_start(message_id)
        yield chunk_start_step()
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

        if text_started:
            yield chunk_text_end(text_id)

        yield chunk_finish_step()
        yield chunk_finish("stop")
        yield STREAM_DONE

    async for chunk in _stream():
        yield chunk


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/chat")
async def ai_gateway_chat(
    request: ChatRequestBody = Body(...),
    version: int = Query(default=1, ge=1, le=2),
    container: "Container" = Depends(get_container(with_user=True)),
    db_session: AsyncSession = Depends(get_session_with_transaction),
):
    """
    Vercel AI SDK **Data Stream** endpoint — compatible with ``useChat``.

    The response uses the data stream protocol (``x-vercel-ai-data-stream: v1``)
    which is the default format consumed by the ``useChat`` React hook.

    **eneo-specific fields** (pass via ``useChat``'s ``body`` option):
    - ``assistant_id`` — UUID of the assistant to start a new conversation
    - ``session_id`` — UUID of an existing session to continue

    A ``[{"session_id": "<uuid>"}]`` data annotation is emitted so the
    frontend can persist the session for follow-up messages.
    """
    response = await _call_conversation_service(request, container, version)
    return StreamingResponse(
        _data_stream(response, db_session),
        media_type="text/plain",
        headers=_DATA_STREAM_HEADERS,
    )


@router.post("/chat-ui")
async def ai_gateway_chat_ui(
    request: ChatRequestBody = Body(...),
    version: int = Query(default=1, ge=1, le=2),
    container: "Container" = Depends(get_container(with_user=True)),
    db_session: AsyncSession = Depends(get_session_with_transaction),
):
    """
    Vercel AI SDK **UI Message Stream** endpoint.

    Uses the named-event SSE protocol (``x-vercel-ai-ui-message-stream: v1``).
    Consumed by the CLI client and tooling that uses ``parseJsonEventStream``.
    """
    response = await _call_conversation_service(request, container, version)
    return StreamingResponse(
        _ui_stream(response, db_session),
        media_type="text/event-stream",
        headers=_UI_STREAM_HEADERS,
    )
