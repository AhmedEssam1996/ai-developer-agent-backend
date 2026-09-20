// Server-Sent Events streaming for agent runs and realtime updates.
// POST-based SSE (the agent endpoint accepts a JSON body) is read manually via
// fetch + ReadableStream. Auth is via the bearer token, never query strings.

import { API_BASE, tokenStore } from "./api";
import type { AgentStreamEvent } from "@/types";

interface StreamHandlers {
  onEvent: (event: AgentStreamEvent) => void;
  onError?: (error: Error) => void;
  onClose?: () => void;
  signal?: AbortSignal;
}

function parseBlock(block: string): AgentStreamEvent | null {
  const dataLines = block
    .split("\n")
    .filter((l) => l.startsWith("data:"))
    .map((l) => l.slice(5).trim());
  if (dataLines.length === 0) return null;
  const raw = dataLines.join("\n");
  if (raw === "[DONE]") return null;
  try {
    return JSON.parse(raw) as AgentStreamEvent;
  } catch {
    return null;
  }
}

function readSseStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: { kind?: string; data?: unknown }) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const onChunk = (): Promise<void> => {
    if (signal?.aborted) return Promise.resolve();
    return reader.read().then(({ done, value }) => {
      if (done) return;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const dataLines = block
          .split("\n")
          .filter((l) => l.startsWith("data:"))
          .map((l) => l.slice(5).trim());
        const raw = dataLines.join("\n");
        if (raw && raw !== "[DONE]") {
          try {
            onEvent(JSON.parse(raw));
          } catch {
            /* ignore malformed frame */
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
      return onChunk();
    });
  };

  return onChunk().finally(() => reader.releaseLock());
}

/** Stream an agent run. Resolves when the stream closes. */
export async function streamAgentRun(
  message: string,
  handlers: StreamHandlers,
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (tokenStore.access) headers.Authorization = `Bearer ${tokenStore.access}`;

  const res = await fetch(`${API_BASE}/api/agent/runs/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message }),
    signal: handlers.signal,
  });

  if (!res.ok || !res.body) {
    let message = "The agent could not start. Please retry.";
    try {
      const payload = await res.json();
      if (payload?.message) message = payload.message;
    } catch {
      /* ignore */
    }
    handlers.onError?.(new Error(message));
    return;
  }

  await readSseStream(res.body, (parsed) => handlers.onEvent(parsed as AgentStreamEvent), handlers.signal)
    .catch((error) => {
      if ((error as Error).name !== "AbortError") {
        handlers.onError?.(error as Error);
      }
    })
    .finally(() => handlers.onClose?.());
}

/** Subscribe to org realtime events via fetch-based SSE. Returns a disposer. */
export function subscribeToEvents(onMessage: (kind: string, data: unknown) => void): () => void {
  let cancelled = false;
  let abortController: AbortController | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  function connect(): void {
    if (cancelled) return;
    const token = tokenStore.access;
    if (!token) return;

    abortController = new AbortController();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    headers.Authorization = `Bearer ${token}`;

    fetch(`${API_BASE}/api/agent/events`, { headers, signal: abortController.signal })
      .then((res) => {
        if (!res.ok || !res.body || cancelled) return;
        readSseStream(res.body, (parsed) => {
          if (!cancelled) onMessage(parsed.kind ?? "message", parsed.data ?? parsed);
        }, abortController?.signal)
          .catch(() => {
            /* connection dropped */
          })
          .finally(() => {
            if (!cancelled) {
              timeoutId = setTimeout(connect, 3000);
            }
          });
      })
      .catch(() => {
        if (!cancelled) {
          timeoutId = setTimeout(connect, 3000);
        }
      });
  }

  connect();

  return () => {
    cancelled = true;
    abortController?.abort();
    if (timeoutId) clearTimeout(timeoutId);
  };
}