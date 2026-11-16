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
  workspace_id?: string | null;  // If set: answer across ALL pages in the workspace
}

export interface Source {
  content: string;       // The chunk text that was retrieved
  chunk_index: number;   // Which chunk it was
  session_id?: string | null;  // Origin tab when answering a workspace
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

// ---------------------------------------------------------------------------
// Workspace (Multi-Tab Knowledge Base) Types
// ---------------------------------------------------------------------------

export interface WorkspacePage {
  session_id: string;
  url: string;
  title: string;
  chunks: number;
  indexed_at: number;
}

export interface Workspace {
  workspace_id: string;
  name: string;
  pages: WorkspacePage[];
  created_at: number;
}

export interface AddPageRequest {
  session_id: string;
  url: string;
  title: string;
  chunks: number;
}
