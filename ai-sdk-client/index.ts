/**
 * Minimal Vercel AI SDK client for the eneo AI gateway.
 *
 * Usage:
 *   bun run chat --assistant <uuid> "Hello, eneo!"
 *   bun run chat --assistant <uuid> --session <uuid> "Continue..."
 *   bun run chat --url http://localhost:8000 --assistant <uuid> "Hi"
 *
 * Authentication:
 *   Set ENEO_API_KEY env var or pass --api-key <key>
 *
 * The eneo backend must be running with the AI gateway endpoint mounted at
 * /api/ai-gateway/chat.
 */

import { parseJsonEventStream, uiMessageChunkSchema } from "ai";
import type { z } from "zod";

// Custom chunk type for eneo-specific data annotations not in the standard schema
type DataSessionChunk = { type: "data-session"; data: { session_id: string } };
type EneoChunk = z.infer<typeof uiMessageChunkSchema> | DataSessionChunk;
import { randomUUID } from "node:crypto";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

interface Config {
  url: string;
  assistantId: string | null;
  sessionId: string | null;
  apiKey: string | null;
  message: string;
}

function parseArgs(argv: string[]): Config {
  const args = argv.slice(2);

  let url = "http://localhost:8000";
  let assistantId: string | null = null;
  let sessionId: string | null = null;
  let apiKey: string | null = process.env.ENEO_API_KEY ?? null;
  let message = "";

  for (let i = 0; i < args.length; i++) {
    if ((args[i] === "--url" || args[i] === "-u") && args[i + 1]) {
      url = args[++i] as string;
    } else if ((args[i] === "--assistant" || args[i] === "-a") && args[i + 1]) {
      assistantId = args[++i] as string;
    } else if ((args[i] === "--session" || args[i] === "-s") && args[i + 1]) {
      sessionId = args[++i] as string;
    } else if ((args[i] === "--api-key" || args[i] === "-k") && args[i + 1]) {
      apiKey = args[++i] as string;
    } else {
      message = args.slice(i).join(" ");
      break;
    }
  }

  if (!message) {
    console.error(
      "Usage: bun run chat [--url <base-url>] [--assistant <uuid>] " +
        "[--session <uuid>] [--api-key <key>] <message>"
    );
    console.error("  ENEO_API_KEY env var can be used instead of --api-key");
    process.exit(1);
  }

  if (!assistantId && !sessionId) {
    console.error("Error: --assistant <uuid> or --session <uuid> is required.");
    process.exit(1);
  }

  return { url, assistantId, sessionId, apiKey, message };
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
  assistant_id?: string;
  session_id?: string;
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

async function chat(config: Config): Promise<void> {
  const { url, assistantId, sessionId, apiKey, message } = config;
  const endpoint = `${url}/api/ai-gateway/chat`;

  const body: SubmitMessageRequest = {
    trigger: "submit-message",
    id: randomUUID(),
    messages: [
      {
        id: randomUUID(),
        role: "user",
        parts: [{ type: "text", text: message }],
      },
    ],
  };

  if (assistantId) body.assistant_id = assistantId;
  if (sessionId) body.session_id = sessionId;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (apiKey) headers["X-API-KEY"] = apiKey;

  console.log(`Sending to ${endpoint}:`);
  console.log(`  > ${message}\n`);

  const response = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }

  const streamHeader = response.headers.get("x-vercel-ai-ui-message-stream");
  if (streamHeader !== "v1") {
    console.warn(
      `Warning: expected x-vercel-ai-ui-message-stream: v1, got: ${streamHeader}`
    );
  }

  if (!response.body) {
    throw new Error("Response has no body");
  }

  const chunkStream = parseJsonEventStream({
    stream: response.body,
    schema: uiMessageChunkSchema,
  });

  process.stdout.write("< ");

  for await (const result of chunkStream) {
    if (!result.success) continue;

    const chunk = result.value as EneoChunk;

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

      default:
        // Print session_id from data-session chunk for conversation continuity
        if (chunk.type === "data-session") {
          const data = (chunk as DataSessionChunk).data;
          if (data?.session_id) {
            process.stdout.write(
              `\n[session: ${data.session_id} — pass --session ${data.session_id} to continue]\n`
            );
            process.stdout.write("< ");
          }
        }
        break;
    }
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const config = parseArgs(process.argv);

chat(config).catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
