/**
 * content.tsx — Chrome Extension Content Script
 *
 * What is a content script?
 *   A content script is JavaScript that Chrome injects into every webpage
 *   you visit (based on the "matches" rule in manifest.json).
 *   It runs in the context of the webpage — it can read the DOM,
 *   add elements, and communicate with the extension's background worker.
 *
 * What does THIS content script do?
 *   1. Creates a container <div> and appends it to the webpage's <body>
 *   2. Attaches a Shadow DOM to that container
 *      (Shadow DOM = isolated mini-document that won't conflict with the page)
 *   3. Mounts our React app inside the Shadow DOM
 *
 * Why Shadow DOM?
 *   Without Shadow DOM, the webpage's CSS might accidentally style our
 *   chatbot (or vice versa). Shadow DOM gives us a completely isolated
 *   styling environment. Think of it as a "bubble" inside the webpage.
 *
 * Data flow:
 *   Chrome injects content.tsx → creates Shadow DOM → mounts React App
 *   → React App renders floating button → user interacts → API calls
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/globals.css';

// ---------------------------------------------------------------------------
// Main injection function
// ---------------------------------------------------------------------------

function injectChatbot(): void {
  // Prevent double injection (e.g. if the script runs twice)
  if (document.getElementById('rag-chatbot-host')) return;

  // Step 1: Create the host element that will hold our Shadow DOM
  const host = document.createElement('div');
  host.id = 'rag-chatbot-host';
  document.body.appendChild(host);

  // Step 2: Attach a Shadow DOM (mode: 'open' means JS can still access it)
  const shadowRoot = host.attachShadow({ mode: 'open' });

  // Step 3: Create a container inside the Shadow DOM for React to mount into
  const container = document.createElement('div');
  container.id = 'rag-chatbot-app';
  shadowRoot.appendChild(container);

  // Step 4: Mount the React app
  const root = ReactDOM.createRoot(container);
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

// Wait for the DOM to be fully ready before injecting
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', injectChatbot);
} else {
  injectChatbot();
}
