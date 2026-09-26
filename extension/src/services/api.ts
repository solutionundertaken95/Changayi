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
} from '../types';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const API_BASE_URL = 'http://127.0.0.1:8000/api';

// ---------------------------------------------------------------------------
// Base fetch helper
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
 * Send a user question to the backend.
 * The backend retrieves relevant chunks and generates an answer via Gemini.
 */
export async function sendMessage(
  request: ChatRequest
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}
