/**
 * session.ts — Generates a stable, unique session ID for the current page.
 *
 * --- WHY DO WE NEED A SESSION ID? ---
 *
 *   The backend stores embeddings in ChromaDB per session.
 *   The session_id is the key that links:
 *     - POST /api/page/index  (store this page's chunks)
 *     - POST /api/chat        (search THIS page's chunks, not another page's)
 *
 *   If two different pages used the same session_id, their chunks would
 *   mix together and answers would be nonsense.
 *
 * --- WHAT MAKES A GOOD SESSION ID HERE? ---
 *
 *   1. URL-based: Different pages → different IDs (no cross-contamination)
 *   2. Stable within a page load: The same ID used for index must be used
 *      for every subsequent chat message on that page.
 *   3. Short and safe: ChromaDB collection names have character restrictions.
 *      Our backend's _collection_name() sanitizes it, but keeping it clean
 *      here too is good practice.
 *
 * --- APPROACH ---
 *
 *   We hash the URL to produce a short, consistent alphanumeric ID.
 *   Same URL → same hash → same session → correct ChromaDB collection.
 *
 *   We use the URL's origin + pathname (excluding query params and hash)
 *   so that ?utm_source=twitter doesn't create a different session for
 *   the same article.
 */

function simpleHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  // Convert to base-36 (alphanumeric) and ensure positive
  return Math.abs(hash).toString(36);
}

export function generateSessionId(): string {
  try {
    const loc = window.location;
    // Use origin + pathname — ignore query params and hash fragments
    // "https://en.wikipedia.org/wiki/Python" → consistent ID regardless of ?section=3
    const stableUrl = loc.origin + loc.pathname;
    return `page-${simpleHash(stableUrl)}`;
  } catch {
    // Fallback for edge cases (e.g. extension pages)
    return `page-${Date.now().toString(36)}`;
  }
}
