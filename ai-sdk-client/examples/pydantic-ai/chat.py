"""
pydantic-ai example using eneo as an OpenAI-compatible provider.

Usage:
    pip install pydantic-ai
    export ENEO_URL=http://localhost:8000       # eneo backend URL
    export ENEO_API_KEY=your-api-key
    export ENEO_ASSISTANT_ID=your-assistant-uuid
    python chat.py "Hello, eneo!"

The eneo AI gateway exposes an OpenAI-compatible endpoint at
/api/v1/ai-gateway/chat/completions, so pydantic-ai can talk to it
via OpenAIProvider with a custom base_url.
"""

from __future__ import annotations

import os
import sys

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


def main() -> None:
    eneo_url = os.environ.get("ENEO_URL", "http://localhost:8000")
    api_key = os.environ.get("ENEO_API_KEY", "")
    assistant_id = os.environ.get("ENEO_ASSISTANT_ID", "")

    if not assistant_id:
        print("Error: set ENEO_ASSISTANT_ID to the UUID of the assistant to chat with.")
        sys.exit(1)

    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello!"

    # Point pydantic-ai at eneo's OpenAI-compatible gateway endpoint.
    # The "model" value is ignored by eneo (the assistant's configured model
    # is used), but OpenAIProvider requires one.
    #
    # The endpoint accepts both Authorization: Bearer <api-key> (which the
    # OpenAI client sends automatically) and X-API-Key: <api-key>.
    model = OpenAIChatModel(
        "eneo",
        provider=OpenAIProvider(
            base_url=f"{eneo_url}/api/v1/ai-gateway",
            api_key=api_key,
        ),
    )

    agent = Agent(
        model,
        system_prompt=(
            "You are chatting via an eneo assistant. "
            "The assistant_id is passed as an extra body field."
        ),
    )

    # pydantic-ai's OpenAIProvider sends standard OpenAI request bodies.
    # eneo's endpoint accepts extra fields (assistant_id, session_id) in
    # the request body thanks to model_config = {"extra": "allow"}.
    # We pass them via model_settings -> openai_extra_body.
    result = agent.run_sync(
        message,
        model_settings={
            "extra_body": {
                "assistant_id": assistant_id,
            },
        },
    )

    print(f"Response: {result.output}")
    print(f"Usage: {result.usage()}")


if __name__ == "__main__":
    main()
