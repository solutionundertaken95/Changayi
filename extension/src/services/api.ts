/**
 * services/api.ts — All communication with the FastAPI backend
 *
 * Why isolate API calls in a service layer?
 *   If the backend URL changes, or we add auth headers, or we switch
 *   from REST to WebSockets for streaming — we change it HERE, not in
 *   every component that makes a request.
 *
 *   The React components should not know or care about fetch() details.
 *   They call a function and get data back. Clean separation of concerns.
 */

import type {
  HealthResponse,
  IndexPageRequest,
  IndexPageResponse,
  ChatRequest,
  ChatResponse,
  Source,
} from '../types';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const API_BASE_URL = 'http://127.0.0.1:8000/api';

// ---------------------------------------------------------------------------
// Base fetch helper (used by non-streaming calls)
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error ${response.status}: ${errorText}`);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * Check if the backend is running.
 * Called before any other operation.
 */
export async function checkHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health');
}

/**
 * Send the current page content to the backend for indexing.
 * The backend will chunk it, embed it, and store it in ChromaDB.
 */
export async function indexPage(
  request: IndexPageRequest
): Promise<IndexPageResponse> {
  return apiFetch<IndexPageResponse>('/page/index', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Send a user question to the backend (non-streaming).
 * The backend retrieves relevant chunks and generates an answer via Gemini.
 * Returns the complete answer as one JSON response.
 */
export async function sendMessage(
  request: ChatRequest
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// ---------------------------------------------------------------------------
// Phase 8 — Streaming API
// ---------------------------------------------------------------------------

/**
 * SSE event types received from POST /api/chat/stream
 *
 * The backend sends newline-delimited JSON over text/event-stream:
 *
 *   data: {"type":"sources","sources":[...]}\n\n   ← arrives first
 *   data: {"type":"chunk","text":"Hello "}\n\n      ← one per Gemini token
 *   data: {"type":"chunk","text":"world"}\n\n
 *   data: {"type":"done"}\n\n                       ← signals end
 *   data: {"type":"error","message":"..."}\n\n      ← if something fails
 */
type StreamEvent =
  | { type: 'sources'; sources: Source[] }
  | { type: 'chunk'; text: string }
  | { type: 'done' }
  | { type: 'error'; message: string };

/**
 * Send a user question to the backend using Server-Sent Events streaming.
 *
 * Instead of waiting for the full answer, this function reads the SSE stream
 * and calls the appropriate callback as each event arrives:
 *
 *   onSources  — called once with the source chunks used to build the answer
 *   onChunk    — called for each token/fragment from Gemini (append to UI)
 *   onDone     — called when streaming is complete
 *   onError    — called if the backend sends an error or fetch fails
 *
 * Why callbacks instead of returning a value?
 *   Streaming is inherently time-distributed — the answer arrives piece by
 *   piece over several seconds. Callbacks let each component react to each
 *   event as it arrives rather than waiting for everything.
 *
 * @param request   The chat request (session_id + question)
 * @param onChunk   Receives each text fragment to append to the AI bubble
 * @param onSources Receives the source chunks array (shown as source cards)
 * @param onDone    Called when the stream ends successfully
 * @param onError   Called if any error occurs during streaming
 */
export async function sendMessageStream(
  request: ChatRequest,
  onChunk: (text: string) => void,
  onSources: (sources: Source[]) => void,
  onDone: () => void,
  onError: (error: Error) => void,
): Promise<void> {
  const url = `${API_BASE_URL}/chat/stream`;

  let response: Response;

  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  } catch (fetchErr) {
    onError(fetchErr instanceof Error ? fetchErr : new Error(String(fetchErr)));
    return;
  }

  if (!response.ok) {
    const errorText = await response.text();
    onError(new Error(`API error ${response.status}: ${errorText}`));
    return;
  }

  // Read the SSE stream using the Fetch ReadableStream API.
  // This is natively available in Chrome extensions (Manifest V3 content
  // scripts run in a Chrome renderer context, not Node.js).
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Decode the bytes into text and append to our line buffer
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by double newlines (\n\n).
      // Split on single newlines — we'll re-join incomplete lines via buffer.
      const lines = buffer.split('\n');
      // The last element is either empty (complete) or an incomplete line
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        // SSE data lines start with "data: "
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;

        let event: StreamEvent;
        try {
          event = JSON.parse(jsonStr) as StreamEvent;
        } catch {
          // Skip malformed lines (shouldn't happen in normal operation)
          continue;
        }

        switch (event.type) {
          case 'sources':
            onSources(event.sources);
            break;
          case 'chunk':
            if (event.text) onChunk(event.text);
            break;
          case 'done':
            onDone();
            return;
          case 'error':
            onError(new Error(event.message ?? 'Streaming error'));
            return;
        }
      }
    }

    // Stream ended without an explicit "done" event — treat as complete
    onDone();
  } catch (readErr) {
    onError(readErr instanceof Error ? readErr : new Error(String(readErr)));
  } finally {
    reader.releaseLock();
  }
}
