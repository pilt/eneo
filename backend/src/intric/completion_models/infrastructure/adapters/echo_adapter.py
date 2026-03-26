"""
Echo completion model adapter.

A fake AI provider for testing and development.  It echoes back the user's
input word-by-word, simulating a streaming LLM response without requiring any
external service or API key.

Usage
-----
To use the echo provider:

1. Create a model provider via the admin API::

       POST /api/admin/model-providers
       {
         "name": "Echo (testing)",
         "provider_type": "echo",
         "credentials": {},
         "config": {}
       }

2. Create a completion model that references the provider::

       POST /api/admin/tenant-models/completion
       {
         "name": "echo",
         "nickname": "Echo",
         "provider_id": "<provider-uuid>",
         "max_input_tokens": 4096,
         "max_output_tokens": 4096,
         ...
       }

3. Assign the echo model to an assistant and start chatting.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncIterator

from intric.ai_models.completion_models.completion_model import (
    Completion,
    ResponseType,
    TokenUsage,
)
from intric.completion_models.infrastructure.adapters.base_adapter import (
    CompletionModelAdapter,
)

if TYPE_CHECKING:
    from intric.ai_models.completion_models.completion_model import (
        CompletionModel,
        Context,
        ModelKwargs,
    )

_TOKEN_DELAY_SECONDS = 0.04  # simulate ~25 tokens/second


class EchoAdapter(CompletionModelAdapter):
    """
    Completion model adapter that echoes back the user's input.

    Requires no credentials or external services.  Intended for development,
    integration testing, and demo environments where real LLM calls are
    not desirable.
    """

    def get_token_limit_of_model(self) -> int:
        return self.model.max_input_tokens

    async def get_response(
        self,
        context: "Context",
        model_kwargs: "ModelKwargs | None" = None,
        mcp_proxy=None,
        **kwargs,
    ) -> Completion:
        reply = f"Echo: {context.input}"
        return Completion(
            text=reply,
            response_type=ResponseType.TEXT,
            stop=True,
            usage=TokenUsage(
                prompt_tokens=len(context.input.split()),
                completion_tokens=len(reply.split()),
            ),
        )

    async def prepare_streaming(
        self,
        context: "Context",
        model_kwargs: "ModelKwargs | None" = None,
        mcp_proxy=None,
        **kwargs,
    ) -> Any:
        """Phase 1: return the context input — no network call needed."""
        return context.input

    async def iterate_stream(  # type: ignore[override]
        self,
        stream: str,
        context: "Context" = None,
        model_kwargs: "ModelKwargs | None" = None,
        require_tool_approval: bool = False,
        approval_manager=None,
    ) -> AsyncIterator[Completion]:
        """Phase 2: yield one Completion per word, then a stop Completion."""
        reply = f"Echo: {stream}"
        words = reply.split(" ")
        total_tokens = len(words)

        for i, word in enumerate(words):
            delta = word if i == 0 else f" {word}"
            yield Completion(
                text=delta,
                response_type=ResponseType.TEXT,
                stop=False,
            )
            await asyncio.sleep(_TOKEN_DELAY_SECONDS)

        yield Completion(
            text="",
            response_type=ResponseType.TEXT,
            stop=True,
            usage=TokenUsage(
                prompt_tokens=len(stream.split()),
                completion_tokens=total_tokens,
            ),
        )
