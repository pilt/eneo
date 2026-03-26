"""
AI gateway router — multiple streaming protocols for eneo assistants.

Three endpoints:

POST /api/ai-gateway/chat
    **Data Stream Protocol** — the format used by the Vercel AI SDK
    ``useChat`` React hook (``streamProtocol: "data"``, the default).
    Response: ``text/plain`` with header ``x-vercel-ai-data-stream: v1``.

POST /api/ai-gateway/chat-ui
    **UI Message Stream Protocol** — named SSE events.
    Response: ``text/event-stream`` with header
    ``x-vercel-ai-ui-message-stream: v1``.
    Used by the CLI client and other tooling that consumes the newer format.

POST /api/ai-gateway/chat/completions
    **OpenAI-compatible** — standard chat completions streaming format.
    Works with pydantic-ai ``OpenAIProvider``, ``openai-python``, LangChain,
    and any other OpenAI-compatible client.

All endpoints:
- Authenticate via the same mechanisms as the rest of the API (Bearer /
  X-API-KEY header)
- Extract the user question from the last ``role: "user"`` message
- Delegate to eneo's ConversationService
- Accept ``assistant_id`` or ``session_id`` via the request body
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterable, Union
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from intric.ai_gateway.protocol import (
    OPENAI_STREAM_DONE,
    STREAM_DONE,
    DS_DONE_HEADER,
    DS_DONE_HEADER_VALUE,
    OpenAIChatRequest,
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
    openai_chat_chunk,
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
                yield ds_finish_step("error", prompt_tokens, completion_tokens)
                yield ds_finish("error", prompt_tokens, completion_tokens)
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
                if text_started:
                    yield chunk_text_end(text_id)
                yield chunk_error(completion.error or "Unknown error")
                yield chunk_finish_step()
                yield chunk_finish("error")
                yield STREAM_DONE
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


# ---------------------------------------------------------------------------
# OpenAI-compatible endpoint  (pydantic-ai, openai-python, etc.)
# ---------------------------------------------------------------------------

_OPENAI_STREAM_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "x-accel-buffering": "no",
}


async def _openai_stream(
    response: "AssistantResponse",
    db_session: AsyncSession,
    model: str,
) -> AsyncIterable[str]:
    chunk_id = f"chatcmpl-{uuid4().hex[:24]}"

    @gen_transaction(db_session)
    async def _stream():
        # Emit initial role chunk
        yield openai_chat_chunk(chunk_id, delta_content="", model=model)

        async for completion in response.answer:
            if completion.response_type == ResponseType.TEXT:
                if completion.text:
                    yield openai_chat_chunk(chunk_id, delta_content=completion.text, model=model)
            elif completion.response_type == ResponseType.ERROR:
                # OpenAI format has no in-stream error; emit as text then stop
                yield openai_chat_chunk(
                    chunk_id,
                    delta_content=f"\n[Error: {completion.error or 'Unknown error'}]",
                    model=model,
                )
                yield openai_chat_chunk(chunk_id, finish_reason="stop", model=model)
                yield OPENAI_STREAM_DONE
                return

        yield openai_chat_chunk(chunk_id, finish_reason="stop", model=model)
        yield OPENAI_STREAM_DONE

    async for chunk in _stream():
        yield chunk


async def _openai_auth_container(
    request: Request,
    db_session: AsyncSession = Depends(get_session_with_transaction),
) -> "Container":
    """
    Custom auth for the OpenAI-compatible endpoint.

    OpenAI clients send ``Authorization: Bearer <key>`` — we extract the
    Bearer value and treat it as an eneo API key so that it works alongside
    the standard ``X-API-Key`` header.
    """
    from dependency_injector import providers
    from intric.main.container.container import Container
    from intric.main.container.container_overrides import override_user
    from intric.users.setup import setup_user

    container = Container(session=providers.Object(db_session))

    # Try X-API-Key header first, then fall back to Bearer token as API key
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if not api_key:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            api_key = auth[7:].strip()

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key.")

    user = await container.user_service().authenticate(api_key=api_key)
    if not user.is_active:
        await setup_user(container=container, user=user)
    override_user(container=container, user=user)
    return container


@router.post("/chat/completions")
async def ai_gateway_openai_chat(
    request: OpenAIChatRequest = Body(...),
    container: "Container" = Depends(_openai_auth_container),
    db_session: AsyncSession = Depends(get_session_with_transaction),
):
    """
    OpenAI-compatible **chat completions** endpoint (streaming).

    Accepts the standard OpenAI request format so that any OpenAI-compatible
    client (pydantic-ai ``OpenAIProvider``, ``openai-python``, LangChain, etc.)
    can talk to eneo assistants.

    Authentication: ``Authorization: Bearer <api-key>`` (OpenAI standard)
    or ``X-API-Key: <api-key>`` (eneo standard). Both are accepted.

    **eneo extensions** (extra fields in the request body):
    - ``assistant_id`` — UUID of the eneo assistant
    - ``session_id`` — UUID of an existing session to continue

    The ``model`` field is accepted but ignored — the assistant's configured
    model is used.
    """
    question = request.last_user_content()
    if not question:
        raise HTTPException(status_code=422, detail="No user message content found.")

    assistant_id = None
    session_id = None
    if request.assistant_id:
        from uuid import UUID as _UUID
        assistant_id = _UUID(request.assistant_id)
    if request.session_id:
        from uuid import UUID as _UUID
        session_id = _UUID(request.session_id)

    if assistant_id is None and session_id is None:
        raise HTTPException(
            status_code=422,
            detail="Either assistant_id or session_id must be provided.",
        )

    response = await container.conversation_service().ask_conversation(
        question=question,
        session_id=session_id,
        assistant_id=assistant_id,
        stream=True,
        version=1,
    )

    if request.stream:
        return StreamingResponse(
            _openai_stream(response, db_session, model=request.model),
            media_type="text/event-stream",
            headers=_OPENAI_STREAM_HEADERS,
        )

    # Non-streaming: collect the full response
    import json as _json
    full_text = ""
    prompt_tokens = 0
    completion_tokens = 0
    async for completion in response.answer:
        if completion.response_type == ResponseType.TEXT and completion.text:
            full_text += completion.text
        if completion.usage:
            prompt_tokens = completion.usage.prompt_tokens or 0
            completion_tokens = completion.usage.completion_tokens or 0

    return {
        "id": f"chatcmpl-{uuid4().hex[:24]}",
        "object": "chat.completion",
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": full_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
