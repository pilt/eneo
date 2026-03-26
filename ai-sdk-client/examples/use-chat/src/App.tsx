/**
 * Minimal eneo chat using the Vercel AI SDK useChat hook.
 *
 * useChat sends POST /api/ai-gateway/chat with the Vercel AI SDK v5
 * UI Message Stream body and parses the SSE response automatically.
 *
 * Configuration (set in your browser's localStorage or via env vars
 * baked in at build time):
 *   VITE_ASSISTANT_ID  — eneo assistant UUID to talk to
 *   VITE_API_KEY       — eneo API key (X-API-KEY header)
 */

import { useChat } from "@ai-sdk/react";
import { FormEvent, useRef, useEffect } from "react";
import "./App.css";

const ASSISTANT_ID = import.meta.env.VITE_ASSISTANT_ID as string | undefined;
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

if (!ASSISTANT_ID) {
  console.warn(
    "VITE_ASSISTANT_ID is not set. Set it in .env.local:\n" +
      "  VITE_ASSISTANT_ID=<your-assistant-uuid>"
  );
}

export default function App() {
  const bottomRef = useRef<HTMLDivElement>(null);

  const { messages, input, handleInputChange, handleSubmit, status, error } =
    useChat({
      // The eneo AI gateway endpoint (proxied via Vite during dev)
      api: "/api/ai-gateway/chat",

      // Pass assistant_id and (optionally) an API key alongside every request.
      // useChat merges these into the request body.
      body: {
        assistant_id: ASSISTANT_ID,
      },
      headers: API_KEY ? { "X-API-KEY": API_KEY } : undefined,

      // Store the session_id returned in the data-session chunk so that
      // follow-up messages continue the same eneo conversation.
      onResponse(response) {
        // useChat handles the stream; we just log non-200 for debugging.
        if (!response.ok) {
          console.error("Gateway error", response.status, response.statusText);
        }
      },
    });

  // Scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const isLoading = status === "streaming" || status === "submitted";

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    handleSubmit(e);
  }

  return (
    <div className="app">
      <header>
        <h1>eneo chat</h1>
        {ASSISTANT_ID && (
          <span className="assistant-id">assistant: {ASSISTANT_ID}</span>
        )}
      </header>

      <main className="messages">
        {messages.length === 0 && (
          <p className="empty">Send a message to start the conversation.</p>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.role}`}>
            <span className="role">{msg.role}</span>
            <div className="content">
              {msg.parts.map((part, i) =>
                part.type === "text" ? (
                  <span key={i}>{part.text}</span>
                ) : null
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="message assistant">
            <span className="role">assistant</span>
            <div className="content thinking">…</div>
          </div>
        )}

        {error && (
          <div className="message error">
            <span className="role">error</span>
            <div className="content">{error.message}</div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      <form className="input-form" onSubmit={submit}>
        <input
          value={input}
          onChange={handleInputChange}
          placeholder={
            ASSISTANT_ID ? "Type a message…" : "Set VITE_ASSISTANT_ID first"
          }
          disabled={!ASSISTANT_ID || isLoading}
          autoFocus
        />
        <button type="submit" disabled={!ASSISTANT_ID || !input.trim() || isLoading}>
          Send
        </button>
      </form>
    </div>
  );
}
