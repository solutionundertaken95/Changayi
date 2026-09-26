/**
 * types/index.ts — Shared TypeScript types for the entire extension
 *
 * Why centralize types?
 *   TypeScript's value is in catching mistakes at compile time.
 *   Centralizing types means if the API response shape changes,
 *   you update it in ONE place and TypeScript flags every broken usage.
 */

// ---------------------------------------------------------------------------
// API Request / Response Types
// ---------------------------------------------------------------------------

export interface IndexPageRequest {
  session_id: string;    // Unique ID for this tab/page session
  url: string;           // The current page URL
  title: string;         // The page title
  content: string;       // The extracted page text
}

export interface IndexPageResponse {
  success: boolean;
  message: string;
  chunks_created: number;
  session_id: string;
}

export interface ChatRequest {
  session_id: string;    // Must match the session_id used when indexing
  question: string;      // What the user asked
}

export interface Source {
  content: string;       // The chunk text that was retrieved
  chunk_index: number;   // Which chunk it was
}

export interface ChatResponse {
  answer: string;        // Gemini's response
  sources: Source[];     // The chunks used to generate the answer
  session_id: string;
}

export interface HealthResponse {
  status: string;
  message: string;
  version: string;
}

// ---------------------------------------------------------------------------
// Chat UI Types
// ---------------------------------------------------------------------------

export type MessageRole = 'user' | 'assistant' | 'error';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  sources?: Source[];    // Only present on assistant messages
}

export type PageStatus = 'idle' | 'indexing' | 'ready' | 'error';
