/**
 * App.tsx
 *
 * Root component mounted by content.tsx into the Shadow DOM.
 *
 * Responsibilities:
 *  - Show the floating "✨ Ask AI" button
 *  - Track whether the chat panel is open or closed
 *  - Reflect the indexing status on the button (analyzing / ready / error)
 *  - Render <ChatPanel> when the panel is open
 *
 * The button ↔ panel toggle is intentionally simple.
 * All chat logic lives inside ChatPanel.
 */

import React, { useState, useEffect } from 'react';
import ChatPanel from './components/ChatPanel';
import { indexingState } from './store/indexingState';
import type { PageStatus } from './types/index';

// ─── Styles for the floating button ──────────────────────────
const BUTTON_STYLES = `
  @keyframes ragButtonPop {
    0%   { transform: scale(0.5); opacity: 0; }
    70%  { transform: scale(1.05); }
    100% { transform: scale(1); opacity: 1; }
  }
  @keyframes ragButtonPulse {
    0%, 100% { box-shadow: 0 4px 20px rgba(99,102,241,0.4); }
    50%       { box-shadow: 0 4px 28px rgba(99,102,241,0.65); }
  }

  .rag-fab {
    animation: ragButtonPop 0.35s cubic-bezier(0.16,1,0.3,1) forwards;
  }
  .rag-fab-ready {
    animation: ragButtonPulse 2.5s ease-in-out infinite;
  }
  .rag-fab:hover {
    transform: scale(1.06) !important;
  }
  .rag-fab:active {
    transform: scale(0.96) !important;
  }
`;

// ─── Button appearance varies by indexing status ──────────────
interface ButtonConfig {
  label: string;
  background: string;
  disabled: boolean;
  title: string;
}

function getButtonConfig(status: PageStatus, isOpen: boolean): ButtonConfig {
  if (isOpen) {
    return {
      label: '✕ Close',
      background: 'linear-gradient(135deg, #6366f1, #7c3aed)',
      disabled: false,
      title: 'Close assistant',
    };
  }
  switch (status) {
    case 'indexing':
      return {
        label: '⏳ Analyzing…',
        background: 'linear-gradient(135deg, #9ca3af, #6b7280)',
        disabled: true,
        title: 'Analyzing page content, please wait…',
      };
    case 'ready':
      return {
        label: '✨ Ask AI',
        background: 'linear-gradient(135deg, #6366f1, #7c3aed)',
        disabled: false,
        title: 'Open Page Assistant',
      };
    case 'error':
      return {
        label: '⚠️ Retry',
        background: 'linear-gradient(135deg, #dc2626, #b91c1c)',
        disabled: false,
        title: 'An error occurred. Click to retry.',
      };
    default: // 'idle'
      return {
        label: '✨ Ask AI',
        background: 'linear-gradient(135deg, #9ca3af, #6b7280)',
        disabled: true,
        title: 'Loading…',
      };
  }
}

// ─────────────────────────────────────────────────────────────
// APP
// ─────────────────────────────────────────────────────────────
const App: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [pageState, setPageState] = useState(indexingState.getState());

  // Subscribe to indexing state changes
  useEffect(() => {
    return indexingState.subscribe(setPageState);
  }, []);

  // When indexing finishes successfully, keep the button alive
  // (do NOT auto-open — the user decides when to chat)
  const btnConfig = getButtonConfig(pageState.status, isOpen);

  const handleButtonClick = () => {
    if (btnConfig.disabled) return;
    setIsOpen((prev) => !prev);
  };

  return (
    <>
      <style>{BUTTON_STYLES}</style>

      {/* ── Floating Action Button ─────────────────────────── */}
      <button
        className={`rag-fab ${pageState.status === 'ready' && !isOpen ? 'rag-fab-ready' : ''}`}
        onClick={handleButtonClick}
        disabled={btnConfig.disabled}
        title={btnConfig.title}
        style={{
          position: 'fixed',
          bottom: 24,
          right: 20,
          height: 48,
          padding: '0 20px',
          background: btnConfig.background,
          color: '#fff',
          border: 'none',
          borderRadius: 24,
          cursor: btnConfig.disabled ? 'not-allowed' : 'pointer',
          fontSize: 14,
          fontWeight: 600,
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          zIndex: 2147483647,
          transition: 'transform 0.15s, box-shadow 0.15s',
          userSelect: 'none',
          whiteSpace: 'nowrap',
          letterSpacing: '0.01em',
        }}
      >
        {btnConfig.label}
      </button>

      {/* ── Chat Panel (rendered when open) ───────────────── */}
      {isOpen && <ChatPanel onClose={() => setIsOpen(false)} />}
    </>
  );
};

export default App;
