"""
Vercel AI SDK UI Message Stream Protocol types.

Request/response models for the AI SDK v5 chat protocol.
See: https://sdk.vercel.ai/docs/ai-sdk-ui/stream-protocol
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class TextPart(BaseModel):
    type: Literal["text"]
    text: str


class FilePart(BaseModel):
    type: Literal["file"]
    url: str
    mediaType: str


# Allow unknown part types to pass through
class UnknownPart(BaseModel):
    type: str
    model_config = {"extra": "allow"}


UIMessagePart = Union[TextPart, FilePart, UnknownPart]


class UIMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system", "tool"]
    parts: list[Any] = Field(default_factory=list)
    model_config = {"extra": "allow"}

    def text_content(self) -> str:
        """Extract plain text from all text parts."""
        texts = []
        for part in self.parts:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif isinstance(part, TextPart):
                texts.append(part.text)
        return "".join(texts)


class SubmitMessageRequest(BaseModel):
    trigger: Literal["submit-message"]
    id: str = Field(default_factory=lambda: str(uuid4()))
    messages: list[UIMessage]
    # eneo-specific fields — pass via useChat's `body` option
    assistant_id: Optional[UUID] = Field(
        default=None,
        description="UUID of the eneo assistant to chat with. "
        "Required when starting a new conversation (no session_id).",
    )
    session_id: Optional[UUID] = Field(
        default=None,
        description="UUID of an existing eneo session to continue.",
    )


class RegenerateMessageRequest(BaseModel):
    trigger: Literal["regenerate-message"]
    id: str = Field(default_factory=lambda: str(uuid4()))
    messageId: str
    messages: list[UIMessage]
    assistant_id: Optional[UUID] = None
    session_id: Optional[UUID] = None


ChatRequest = Union[SubmitMessageRequest, RegenerateMessageRequest]


# ---------------------------------------------------------------------------
# SSE chunk helpers
# ---------------------------------------------------------------------------

STREAM_DONE = "data: [DONE]\n\n"


def _chunk(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"


def chunk_start(message_id: str) -> str:
    return _chunk({"type": "start", "messageId": message_id})


def chunk_start_step() -> str:
    return _chunk({"type": "start-step"})


def chunk_text_start(text_id: str) -> str:
    return _chunk({"type": "text-start", "id": text_id})


def chunk_text_delta(text_id: str, delta: str) -> str:
    return _chunk({"type": "text-delta", "id": text_id, "delta": delta})


def chunk_text_end(text_id: str) -> str:
    return _chunk({"type": "text-end", "id": text_id})


def chunk_finish_step() -> str:
    return _chunk({"type": "finish-step"})


def chunk_finish(finish_reason: str = "stop") -> str:
    return _chunk({"type": "finish", "finishReason": finish_reason})


def chunk_error(error_text: str) -> str:
    return _chunk({"type": "error", "errorText": error_text})


def chunk_data(name: str, data: Any) -> str:
    """Custom typed data chunk (type must match `data-*` pattern)."""
    return _chunk({"type": f"data-{name}", "data": data})
