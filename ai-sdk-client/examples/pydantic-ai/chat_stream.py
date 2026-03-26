"""
pydantic-ai streaming example using eneo as an OpenAI-compatible provider.

Usage:
    pip install pydantic-ai
    export ENEO_URL=http://localhost:8000
    export ENEO_API_KEY=your-api-key
    export ENEO_ASSISTANT_ID=your-assistant-uuid
    python chat_stream.py "Tell me something interesting"

Demonstrates streaming responses from an eneo assistant via pydantic-ai.
"""

from __future__ import annotations

import asyncio
import os
import sys

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


async def main() -> None:
    eneo_url = os.environ.get("ENEO_URL", "http://localhost:8000")
    api_key = os.environ.get("ENEO_API_KEY", "")
    assistant_id = os.environ.get("ENEO_ASSISTANT_ID", "")

    if not assistant_id:
        print("Error: set ENEO_ASSISTANT_ID to the UUID of the assistant to chat with.")
        sys.exit(1)

    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello!"

    # The endpoint accepts Authorization: Bearer <api-key> (standard OpenAI auth)
    model = OpenAIChatModel(
        "eneo",
        provider=OpenAIProvider(
            base_url=f"{eneo_url}/api/v1/ai-gateway",
            api_key=api_key,
        ),
    )

    agent = Agent(
        model,
        system_prompt="You are chatting via an eneo assistant.",
    )

    print(f"> {message}\n")

    async with agent.run_stream(
        message,
        model_settings={
            "extra_body": {
                "assistant_id": assistant_id,
            },
        },
    ) as stream:
        async for chunk in stream.stream_text():
            print(chunk, end="", flush=True)

    print(f"\n\n[Usage: {stream.usage()}]")


if __name__ == "__main__":
    asyncio.run(main())
