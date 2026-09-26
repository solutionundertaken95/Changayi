/**
 * content.tsx — Chrome Extension Content Script
 *
 * ISOLATION STRATEGY (why each choice was made):
 *
 * Problem: our injected <div> lives inside the page's DOM and inherits
 * the page's CSS rules. This causes misalignment on sites that use
 * flex/grid on body, transforms, CSS resets, etc.
 *
 * Fix — three layers:
 *
 * Layer 1: Inject a <style> tag into the page's <head> targeting our host by ID.
 *   Why a <style> tag instead of element.style.cssText?
 *   → element.style.cssText does NOT reliably support !important in JavaScript.
 *     Browsers strip !important from programmatically set inline styles.
 *     A <style> tag in the document IS a real stylesheet and !important works.
 *
 * Layer 2: Append host to document.documentElement (the <html> tag), not body.
 *   Why not body?
 *   → If body has `transform`, `perspective`, or `filter`, position:fixed elements
 *     inside it are positioned relative to body, not the viewport.
 *     The <html> element almost never has these transforms.
 *
 * Layer 3: Shadow DOM inside the host.
 *   → Isolates all internal CSS from the page. Page styles can't reach inside.
 *     Internal styles can't leak out to the page.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

function injectChatbot(): void {
  if (document.getElementById('rag-chatbot-host')) return;

  // ── Layer 1: Inject page-level stylesheet for the host element ────────
  // This is a real stylesheet — !important here genuinely wins over
  // any page CSS that targets div, *, or even our #rag-chatbot-host id.
  const pageStyle = document.createElement('style');
  pageStyle.id = 'rag-chatbot-host-style';
  pageStyle.textContent = `
    #rag-chatbot-host {
      /* Remove from layout entirely */
      position: fixed !important;
      top: 0 !important;
      left: 0 !important;
      width: 0 !important;
      height: 0 !important;
      overflow: visible !important;

      /* Always on top */
      z-index: 2147483647 !important;

      /* Don't block page interactions */
      pointer-events: none !important;

      /* Reset everything that could be inherited or set by page CSS */
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
      clear: none !important;
      vertical-align: baseline !important;
      max-width: none !important;
      max-height: none !important;
      min-width: 0 !important;
      min-height: 0 !important;
    }
  `;
  // Append to <head> if available, otherwise to <html>
  (document.head || document.documentElement).appendChild(pageStyle);

  // ── Layer 2: Host element appended to <html>, not <body> ──────────────
  // Appending to documentElement avoids body transforms (common in SPAs).
  const host = document.createElement('div');
  host.id = 'rag-chatbot-host';
  document.documentElement.appendChild(host);

  // ── Layer 3: Shadow DOM ───────────────────────────────────────────────
  const shadowRoot = host.attachShadow({ mode: 'open' });

  // Reset CSS inside the shadow root — protects against any inheritance
  // that leaks through the shadow boundary (e.g. font, color, line-height)
  const shadowStyle = document.createElement('style');
  shadowStyle.textContent = `
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    :host {
      all: initial;
      display: block;
      position: fixed;
      top: 0;
      left: 0;
      width: 0;
      height: 0;
      overflow: visible;
      pointer-events: none;
    }

    #rag-chatbot-app {
      display: block;
      width: 0;
      height: 0;
      overflow: visible;
      pointer-events: none;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: #1e293b;
    }
  `;
  shadowRoot.appendChild(shadowStyle);

  // ── Mount React ───────────────────────────────────────────────────────
  const container = document.createElement('div');
  container.id = 'rag-chatbot-app';
  shadowRoot.appendChild(container);

  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

// Run after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', injectChatbot);
} else {
  injectChatbot();
}
