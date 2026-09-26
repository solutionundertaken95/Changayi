/**
 * indexingState.ts — Shared state between the content script and React app.
 *
 * --- THE COMMUNICATION PROBLEM ---
 *
 *   content.tsx runs two things concurrently:
 *     1. Renders the React app (synchronous — button appears immediately)
 *     2. Indexes the page via the backend (async — takes a few seconds)
 *
 *   Once indexing finishes, the React UI needs to know so it can:
 *     - Change the button from "Analyzing..." → "✨ Ask AI"
 *     - Store the session_id so chat requests use the right ChromaDB collection
 *     - Show the user that the page is ready
 *
 *   But content.tsx (outside React) and App.tsx (inside React) can't
 *   directly call each other — they're separate modules.
 *
 * --- THE SOLUTION: A simple pub/sub state singleton ---
 *
 *   This module is a single shared object in memory.
 *   - content.tsx calls indexingState.update() when indexing completes
 *   - App.tsx calls indexingState.subscribe() in a useEffect to listen for changes
 *
 *   This pattern is called "observer" or "pub/sub" (publish/subscribe).
 *   It's a minimal version of what Redux or Zustand do — but without the
 *   overhead, since we only have one piece of state to share.
 *
 * --- STATE LIFECYCLE ---
 *
 *   idle      → Page loaded, extraction hasn't started yet
 *   indexing  → Extraction done, waiting for backend to embed + store
 *   ready     → Backend confirmed success — user can now chat
 *   error     → Something went wrong (backend offline, page too short, etc.)
 */

export type IndexingStatus = 'idle' | 'indexing' | 'ready' | 'error';

export interface IndexingState {
  status: IndexingStatus;
  sessionId: string;
  message: string;
  pageTitle: string;
}

type Listener = (state: IndexingState) => void;

class IndexingStateManager {
  private state: IndexingState = {
    status: 'idle',
    sessionId: '',
    message: '',
    pageTitle: '',
  };

  private listeners: Listener[] = [];

  /** Update the state and notify all subscribers. */
  update(partial: Partial<IndexingState>): void {
    this.state = { ...this.state, ...partial };
    this.listeners.forEach(listener => listener(this.state));
  }

  /**
   * Subscribe to state changes.
   * Returns an unsubscribe function — call it in useEffect cleanup
   * to avoid memory leaks when the React component unmounts.
   *
   * Usage in React:
   *   useEffect(() => {
   *     const unsub = indexingState.subscribe(state => setStatus(state));
   *     return unsub; // cleanup on unmount
   *   }, []);
   */
  subscribe(listener: Listener): () => void {
    this.listeners.push(listener);
    // Immediately call with current state so new subscribers are up to date
    listener(this.state);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  getState(): IndexingState {
    return this.state;
  }
}

// Single shared instance — imported by both content.tsx and App.tsx
export const indexingState = new IndexingStateManager();
