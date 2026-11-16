/**
 * content.tsx — Chrome Extension Content Script
 *
 * What this script does:
 *   1. Injects the React chatbot UI into every webpage
 *   2. Exposes ON-DEMAND page indexing — NOTHING is indexed automatically
 *   3. Updates shared state so the React UI knows when it's ready
 *
 * ─── INDEXING POLICY (changed from auto-indexing) ───
 *
 *   BEFORE: every page load (and every SPA navigation) silently fired
 *   POST /api/page/index — "Analyzing…" appeared on every site visited.
 *
 *   NOW: the page is indexed ONLY when the user asks for it:
 *     - sending the first question in the panel, or
 *     - clicking "Add to Knowledge Base" (workspace)
 *
 *   Execution order when indexing IS requested:
 *   ┌─────────────────────────────────────────────┐
 *   │ Page loads → mount React (button shows)     │
 *   │   ↓  (nothing else happens — zero indexing) │
 *   │ User opens panel / asks a question          │
 *   │   ↓                                         │
 *   │ ensureIndexed() → POST /api/page/index      │
 *   │   ↓                                         │
 *   │ indexingState → 'ready' → chat flows        │
 *   └─────────────────────────────────────────────┘
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { extractPageContent } from './utils/extractor';
import { generateSessionId } from './utils/session';
import { indexingState } from './store/indexingState';
import { indexPage } from './services/api';

// ---------------------------------------------------------------------------
// DOM injection (same isolation strategy from the bug fix)
// ---------------------------------------------------------------------------

function injectChatbot(): void {
  if (document.getElementById('rag-chatbot-host')) return;

  // Inject page-level stylesheet for the host element
  const pageStyle = document.createElement('style');
  pageStyle.id = 'rag-chatbot-host-style';
  pageStyle.textContent = `
    #rag-chatbot-host {
      position: fixed !important;
      top: 0 !important;
      left: 0 !important;
      width: 0 !important;
      height: 0 !important;
      overflow: visible !important;
      z-index: 2147483647 !important;
      margin: 0 !important;
      padding: 0 !important;
      border: none !important;
      outline: none !important;
      background: none !important;
      box-shadow: none !important;
      transform: none !important;
      filter: none !important;
      opacity: 1 !important;
      visibility: visible !important;
      display: block !important;
      float: none !important;
    }
  `;
  (document.head || document.documentElement).appendChild(pageStyle);

  // Append to <html>, not <body> (avoids body transform issues)
  const host = document.createElement('div');
  host.id = 'rag-chatbot-host';
  document.documentElement.appendChild(host);

  const shadowRoot = host.attachShadow({ mode: 'open' });

  const shadowStyle = document.createElement('style');
  shadowStyle.textContent = `
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :host {
      all: initial;
      display: block;
      position: fixed;
      top: 0; left: 0;
      width: 0; height: 0;
      overflow: visible;
    }
    #rag-chatbot-app {
      display: block;
      width: 0; height: 0;
      overflow: visible;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: #1e293b;
    }
  `;
  shadowRoot.appendChild(shadowStyle);

  const container = document.createElement('div');
  container.id = 'rag-chatbot-app';
  shadowRoot.appendChild(container);

  // ── Step 1: Mount React immediately ─────────────────────────────────
  // The button appears right away — the user doesn't wait for indexing.
  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );

  // ── Step 2: NO automatic indexing.
  // The page is indexed only when the user explicitly acts
  // (asks a question or adds it to a workspace) — see ensureIndexed().
}

// ---------------------------------------------------------------------------
// On-demand indexing pipeline
// ---------------------------------------------------------------------------

// Guards against concurrent indexing (e.g., rapid SPA navigations)
let isIndexing = false;

// The URL that was last indexed — used to detect stale sessions after
// SPA navigation. Question-triggered indexing always re-checks this.
let lastIndexedUrl: string | null = null;

async function ensureIndexed(): Promise<boolean> {
  // Re-check URL: if SPA navigation happened after the last successful
  // index, this session is stale and must be re-run for the new page.
  if (lastIndexedUrl === window.location.href) return true;

  if (isIndexing) return false;
  isIndexing = true;

  const sessionId = generateSessionId();

  try {
    // Signal: extraction starting
    indexingState.update({
      status: 'indexing',
      sessionId,
      message: 'Reading page content...',
      pageTitle: document.title,
    });

    // Extract text from the live DOM
    const extracted = extractPageContent();

    if (extracted.wordCount < 30) {
      // Page has almost no readable content (maybe a login page, blank page, etc.)
      indexingState.update({
        status: 'error',
        sessionId,
        message: 'Not enough content on this page to analyze.',
        pageTitle: extracted.title,
      });
      return;
    }

    // Signal: sending to backend
    indexingState.update({
      status: 'indexing',
      sessionId,
      message: `Analyzing ${extracted.wordCount.toLocaleString()} words...`,
      pageTitle: extracted.title,
    });

    // POST to FastAPI → clean → chunk → embed → store in ChromaDB
    const result = await indexPage({
      session_id: sessionId,
      url: extracted.url,
      title: extracted.title,
      content: extracted.text,
    });

    if (result.success) {
      lastIndexedUrl = window.location.href;
      indexingState.update({
        status: 'ready',
        sessionId,
        message: `Ready — ${result.chunks_created} sections indexed`,
        pageTitle: extracted.title,
      });
    } else {
      throw new Error(result.message || 'Indexing failed');
    }

  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    console.error('[RAG Chatbot] Indexing error:', message);

    // Check if it's a connection error (backend not running)
    const isConnectionError = message.includes('fetch') || message.includes('network') || message.includes('Failed to fetch');

    indexingState.update({
      status: 'error',
      sessionId,
      message: isConnectionError
        ? 'Cannot connect to backend. Is the Python server running?'
        : `Error: ${message}`,
      pageTitle: document.title,
    });
    return false;
  } finally {
    isIndexing = false;
  }
  return true;
}

// Expose for React components (ChatPanel) which need to trigger
// indexing on user action.
(window as unknown as { ragEnsureIndexed: () => Promise<boolean> }).ragEnsureIndexed =
  ensureIndexed;

// ---------------------------------------------------------------------------
// SPA Navigation Detection — STALENESS ONLY (no auto re-index)
// ---------------------------------------------------------------------------
//
//   Single-Page Applications change the URL via history.pushState() WITHOUT
//   reloading. We do NOT auto-index on navigation (old behavior). We only
//   mark the session stale, so the next user ACTION (question / add-to-KB)
//   re-indexes the new page first.
// ---------------------------------------------------------------------------

let currentUrl = window.location.href;

function handleUrlChange(): void {
  const newUrl = window.location.href;
  if (newUrl === currentUrl) return; // Hash-only or duplicate — ignore
  currentUrl = newUrl;

  // Invalidate the index for the old page. Nothing is fetched or POSTed
  // here — indexing happens on the user's next explicit action.
  lastIndexedUrl = null;
  indexingState.update({
    status: 'idle',
    message: 'Page changed — content will be analyzed on your next action.',
    pageTitle: document.title,
  });
}

// Intercept pushState (most SPA navigation)
const _origPushState = history.pushState.bind(history);
history.pushState = function (...args: Parameters<typeof history.pushState>) {
  _origPushState(...args);
  handleUrlChange();
};

// Intercept replaceState (e.g. YouTube updates URL as video plays)
const _origReplaceState = history.replaceState.bind(history);
history.replaceState = function (...args: Parameters<typeof history.replaceState>) {
  _origReplaceState(...args);
  handleUrlChange();
};

// Back/Forward browser buttons
window.addEventListener('popstate', handleUrlChange);

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', injectChatbot);
} else {
  injectChatbot();
}
