/**
 * content.tsx — Chrome Extension Content Script (Phase 4)
 *
 * What this script does now:
 *   1. Injects the React chatbot UI into every webpage (Phase 1)
 *   2. Extracts the page's readable text (Phase 4 — NEW)
 *   3. Sends it to the FastAPI backend for indexing (Phase 4 — NEW)
 *   4. Updates shared state so the React UI knows when it's ready (Phase 4 — NEW)
 *
 * Execution order (important for UX):
 *   ┌─────────────────────────────────────────────┐
 *   │ Page loads                                  │
 *   │   ↓                                         │
 *   │ Mount React app  ← IMMEDIATE (button shows) │
 *   │   ↓                                         │
 *   │ Extract page text (fast, DOM read)           │
 *   │   ↓                                         │
 *   │ POST /api/page/index (async, ~2-5 seconds)  │
 *   │   ↓                                         │
 *   │ indexingState → 'ready'                     │
 *   │   ↓                                         │
 *   │ React re-renders: button activates          │
 *   └─────────────────────────────────────────────┘
 *
 * The user sees the button immediately. While the backend processes the page,
 * the button shows a subtle "analyzing" state. When it's ready, the button
 * lights up and the user can start asking questions.
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

  // ── Step 2: Index the page in the background ─────────────────────────
  // We don't await this — it runs concurrently with the mounted React app.
  indexCurrentPage();
}

// ---------------------------------------------------------------------------
// Page indexing pipeline
// ---------------------------------------------------------------------------

// Guards against concurrent indexing (e.g., rapid SPA navigations)
let isIndexing = false;

async function indexCurrentPage(): Promise<void> {
  if (isIndexing) return;
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
  } finally {
    isIndexing = false;
  }
}

// ---------------------------------------------------------------------------
// SPA Navigation Detection
// ---------------------------------------------------------------------------
//
// The Problem:
//   Single-Page Applications (GitHub, YouTube, Medium, Twitter/X) change the
//   URL via JavaScript — history.pushState() — WITHOUT reloading the page.
//   Chrome only runs content scripts on actual page loads, so our script would
//   keep answering questions about the OLD page even after the user navigates.
//
// The Fix:
//   We intercept the three ways a URL can change without a page reload:
//     1. history.pushState()    — SPA "click a link" navigation
//     2. history.replaceState() — SPA "update URL without history entry"
//     3. popstate event         — Browser back/forward buttons
//
// When a URL change is detected:
//   - Wait 600ms for the new page's DOM to settle
//   - Re-run the indexing pipeline for the new URL

let currentUrl = window.location.href;

function handleUrlChange(): void {
  const newUrl = window.location.href;
  if (newUrl === currentUrl) return; // Hash-only or duplicate — ignore
  currentUrl = newUrl;

  console.log('[RAG Chatbot] URL changed → re-indexing:', newUrl);

  // Small delay so the SPA can render the new page's DOM
  setTimeout(() => {
    indexCurrentPage();
  }, 600);
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
