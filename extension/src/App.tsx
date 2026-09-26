/**
 * App.tsx — Root React component (Phase 4)
 *
 * New in Phase 4:
 *   - Subscribes to indexingState — knows when the page is ready
 *   - Button reflects current status (idle → analyzing → ready → error)
 *   - Stores sessionId from the shared state (needed for /api/chat in Phase 5)
 *   - Panel shows page title and status message
 *
 * Phase 5 will replace the placeholder panel with the full chat UI.
 * The sessionId stored here will be passed into the chat components.
 */

import React, { useState, useEffect } from 'react';
import { indexingState, IndexingState } from './store/indexingState';

const App: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [state, setState] = useState<IndexingState>(indexingState.getState());

  // Subscribe to indexing state changes from content.tsx
  useEffect(() => {
    const unsubscribe = indexingState.subscribe(newState => {
      setState(newState);
    });
    return unsubscribe; // Cleanup subscription on unmount
  }, []);

  // Derived values for the UI
  const isReady    = state.status === 'ready';
  const isIndexing = state.status === 'indexing' || state.status === 'idle';
  const isError    = state.status === 'error';

  const buttonLabel = isReady
    ? '✨ Ask AI'
    : isError
    ? '⚠️ Error'
    : '⏳ Analyzing...';

  const buttonColor = isError
    ? '#ef4444'   // red
    : isReady
    ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'  // indigo/purple
    : '#94a3b8';  // grey (loading)

  return (
    <>
      {/* ── Floating button ─────────────────────────────── */}
      <button
        onClick={() => setIsOpen(prev => !prev)}
        disabled={isIndexing}
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          zIndex: 2147483647,
          pointerEvents: 'auto',
          background: buttonColor,
          color: '#fff',
          border: 'none',
          borderRadius: '50px',
          padding: '12px 20px',
          fontSize: '14px',
          fontWeight: '600',
          cursor: isIndexing ? 'wait' : 'pointer',
          boxShadow: isReady
            ? '0 4px 24px rgba(99, 102, 241, 0.45)'
            : '0 4px 16px rgba(0,0,0,0.15)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          transition: 'all 0.3s ease',
          userSelect: 'none',
          whiteSpace: 'nowrap',
          opacity: isIndexing ? 0.85 : 1,
        }}
      >
        {buttonLabel}
      </button>

      {/* ── Status / placeholder panel ───────────────────── */}
      {isOpen && (
        <div
          style={{
            position: 'fixed',
            bottom: '80px',
            right: '24px',
            width: '360px',
            background: '#fff',
            borderRadius: '16px',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.15)',
            overflow: 'hidden',
            zIndex: 2147483646,
            pointerEvents: 'auto',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          }}
        >
          {/* Panel header */}
          <div style={{
            padding: '16px 20px',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div>
              <div style={{ fontWeight: '700', color: '#1e293b', fontSize: '15px' }}>
                RAG Chatbot
              </div>
              <div style={{
                fontSize: '12px',
                color: '#64748b',
                marginTop: '2px',
                maxWidth: '260px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {state.pageTitle || window.location.hostname}
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#94a3b8',
                fontSize: '18px',
                lineHeight: 1,
                padding: '4px',
              }}
            >
              ✕
            </button>
          </div>

          {/* Status body */}
          <div style={{ padding: '24px 20px' }}>
            {isIndexing && (
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  width: '40px', height: '40px',
                  border: '3px solid #e2e8f0',
                  borderTop: '3px solid #6366f1',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                  margin: '0 auto 16px',
                }} />
                <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                <p style={{ color: '#475569', fontSize: '14px' }}>
                  {state.message || 'Reading page content...'}
                </p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '8px' }}>
                  This takes a few seconds on first load
                </p>
              </div>
            )}

            {isReady && (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '32px', marginBottom: '12px' }}>✅</div>
                <p style={{ color: '#1e293b', fontWeight: '600', fontSize: '15px' }}>
                  Page analyzed!
                </p>
                <p style={{ color: '#64748b', fontSize: '13px', marginTop: '6px' }}>
                  {state.message}
                </p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '16px' }}>
                  Full chat UI coming in Phase 5
                </p>
              </div>
            )}

            {isError && (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚠️</div>
                <p style={{ color: '#ef4444', fontWeight: '600', fontSize: '14px' }}>
                  {state.message}
                </p>
                {state.message.includes('backend') && (
                  <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '8px' }}>
                    Run: uvicorn app.main:app --reload
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default App;
