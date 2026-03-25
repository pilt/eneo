/**
 * Minimal Vercel AI SDK client for the eneo AI gateway.
 *
 * Usage:
 *   bun run index.ts "Hello, world!"
 *   bun run index.ts --url http://localhost:8000 "Tell me a joke"
 *
 * The eneo backend must be running and the AI gateway endpoint must be
 * mounted at /api/ai-gateway/chat (default when using the echo adapter).
 */

import { parseJsonEventStream, uiMessageChunkSchema } from "ai";
import { randomUUID } from "node:crypto";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

function parseArgs(argv: string[]): { url: string; message: string } {
  const args = argv.slice(2); // drop "bun" and script path

  let url = "http://localhost:8000";
  let message = "";

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--url" && args[i + 1]) {
      url = args[++i] as string;
    } else {
      message = args.slice(i).join(" ");
      break;
    }
  }

  if (!message) {
    console.error("Usage: bun run index.ts [--url <base-url>] <message>");
    process.exit(1);
  }

  return { url, message };
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UIMessagePart {
  type: string;
  text?: string;
}

interface UIMessage {
  id: string;
  role: "user" | "assistant" | "system";
  parts: UIMessagePart[];
}

interface SubmitMessageRequest {
  trigger: "submit-message";
  id: string;
  messages: UIMessage[];
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

async function chat(baseUrl: string, userMessage: string): Promise<void> {
  const endpoint = `${baseUrl}/api/ai-gateway/chat`;

  const body: SubmitMessageRequest = {
    trigger: "submit-message",
    id: randomUUID(),
    messages: [
      {
        id: randomUUID(),
        role: "user",
        parts: [{ type: "text", text: userMessage }],
      },
    ],
  };

  console.log(`Sending to ${endpoint}:`);
  console.log(`  > ${userMessage}\n`);

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }

  // Verify the response speaks the UI message stream protocol
  const streamHeader = response.headers.get("x-vercel-ai-ui-message-stream");
  if (streamHeader !== "v1") {
    console.warn(
      `Warning: expected x-vercel-ai-ui-message-stream: v1, got: ${streamHeader}`
    );
  }

  if (!response.body) {
    throw new Error("Response has no body");
  }

  // Parse the UI message stream using the AI SDK
  const chunkStream = parseJsonEventStream({
    stream: response.body,
    schema: uiMessageChunkSchema,
  });

  process.stdout.write("< ");

  for await (const result of chunkStream) {
    if (!result.success) continue;

    const chunk = result.value;

    switch (chunk.type) {
      case "text-delta":
        process.stdout.write(chunk.delta);
        break;

      case "error":
        process.stderr.write(`\nError from server: ${chunk.errorText}\n`);
        break;

      case "finish":
        process.stdout.write(
          `\n\n[done — finish reason: ${chunk.finishReason ?? "stop"}]\n`
        );
        break;

      // Ignore control chunks (start, start-step, finish-step, text-start, text-end)
      default:
        break;
    }
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const { url, message } = parseArgs(process.argv);

chat(url, message).catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
