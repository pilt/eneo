"""
Simulator completion model adapter.

A configurable fake AI provider for testing and development.  It requires no
external service or API key.  The response behaviour is controlled by the
``strategy`` field in the model provider's ``config``.

Available strategies
--------------------
``echo`` (default)
    Streams back "Echo: {input}" word-by-word.  Good for verifying that text
    arrives at the client correctly.

More strategies can be added here as testing needs grow (e.g. ``static`` for
a fixed canned response, ``slow`` to simulate high latency, ``error`` to
intentionally raise mid-stream, etc.).

Usage
-----
1. Create a model provider via the admin API::

       POST /api/admin/model-providers
       {
         "name": "Simulator (testing)",
         "provider_type": "simulator",
         "credentials": {},
         "config": {"strategy": "echo"}
       }

2. Create a completion model that references the provider::

       POST /api/admin/tenant-models/completion
       { "name": "simulator-echo", "provider_id": "<uuid>", ... }

3. Assign the model to an assistant — responses will be simulated locally.
"""

from __future__ import annotations

import asyncio
from enum import Enum
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

_DEFAULT_TOKEN_DELAY = 0.04  # ~25 tokens/second, used when token_delay not set


class SimulationStrategy(str, Enum):
    ECHO = "echo"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "SimulationStrategy":
        """Parse strategy from provider config, defaulting to ECHO."""
        raw = config.get("strategy", "echo")
        try:
            return cls(raw)
        except ValueError:
            raise ValueError(
                f"Unknown simulation strategy '{raw}'. "
                f"Valid strategies: {[s.value for s in cls]}"
            )


class SimulatorAdapter(CompletionModelAdapter):
    """
    Completion model adapter that simulates LLM responses locally.

    The response behaviour is controlled by the ``strategy`` argument,
    which maps to a ``SimulationStrategy`` value.  Use
    ``SimulationStrategy.from_config(provider_db.config)`` when constructing
    from a provider database row.
    """

    def __init__(
        self,
        model: "CompletionModel",
        strategy: SimulationStrategy = SimulationStrategy.ECHO,
        token_delay: float = _DEFAULT_TOKEN_DELAY,
    ):
        super().__init__(model)
        self.strategy = strategy
        self.token_delay = token_delay

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_reply(self, input_text: str) -> str:
        if self.strategy == SimulationStrategy.ECHO:
            return f"Echo: {input_text}"
        # Unreachable once new strategies are added and handled above,
        # but kept as a safety net.
        raise NotImplementedError(f"Strategy '{self.strategy}' not implemented")

    # ------------------------------------------------------------------
    # CompletionModelAdapter interface
    # ------------------------------------------------------------------

    def get_token_limit_of_model(self) -> int:
        return self.model.max_input_tokens

    async def get_response(
        self,
        context: "Context",
        model_kwargs: "ModelKwargs | None" = None,  # interface compatibility
        mcp_proxy=None,  # interface compatibility
        **kwargs,
    ) -> Completion:
        reply = self._generate_reply(context.input)
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
        model_kwargs: "ModelKwargs | None" = None,  # interface compatibility
        mcp_proxy=None,  # interface compatibility
        **kwargs,
    ) -> Any:
        """Phase 1: validate strategy and return context input for Phase 2."""
        # Validate now so any misconfiguration raises before HTTP 200 is sent.
        self._generate_reply(context.input)
        return context.input

    async def iterate_stream(  # type: ignore[override]
        self,
        stream: str,
        context: "Context" = None,  # interface compatibility
        model_kwargs: "ModelKwargs | None" = None,  # interface compatibility
        require_tool_approval: bool = False,  # interface compatibility
        approval_manager=None,  # interface compatibility
    ) -> AsyncIterator[Completion]:
        """Phase 2: yield one Completion per word, then a stop Completion."""
        reply = self._generate_reply(stream)
        words = reply.split()

        for i, word in enumerate(words):
            delta = word if i == 0 else f" {word}"
            yield Completion(
                text=delta,
                response_type=ResponseType.TEXT,
                stop=False,
            )
            if self.token_delay > 0:
                await asyncio.sleep(self.token_delay)

        yield Completion(
            text="",
            response_type=ResponseType.TEXT,
            stop=True,
            usage=TokenUsage(
                prompt_tokens=len(stream.split()),
                completion_tokens=len(words),
            ),
        )
