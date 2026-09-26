/**
 * App.tsx — Root React component (Phase 1 placeholder)
 *
 * Because the host element and shadow container both have
 * pointer-events: none, every interactive element here MUST
 * explicitly set pointer-events: auto, or clicks will pass through.
 *
 * All elements use position: fixed with explicit viewport coordinates
 * so they render correctly regardless of the host's own position.
 */

import React, { useState } from 'react';

const App: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* ── Floating button ─────────────────────────────────── */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          // Viewport positioning — independent of any parent element
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          zIndex: 2147483647,

          // Re-enable pointer events (host has pointer-events: none)
          pointerEvents: 'auto',

          // Visual styling
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          color: '#fff',
          border: 'none',
          borderRadius: '50px',
          padding: '12px 20px',
          fontSize: '14px',
          fontWeight: '600',
          cursor: 'pointer',
          boxShadow: '0 4px 24px rgba(99, 102, 241, 0.45)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          transition: 'transform 0.15s ease, box-shadow 0.15s ease',
          userSelect: 'none',
          whiteSpace: 'nowrap',
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)';
          (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 8px 32px rgba(99, 102, 241, 0.55)';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)';
          (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 24px rgba(99, 102, 241, 0.45)';
        }}
      >
        ✨ Sughalle ?
      </button>

      {/* ── Placeholder panel ───────────────────────────────── */}
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
            padding: '24px',
            zIndex: 2147483646,

            // Re-enable pointer events
            pointerEvents: 'auto',

            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          }}
        >
          <h3 style={{ marginBottom: '8px', color: '#1e293b', fontSize: '16px' }}>
            🎉 Phase 1 Complete!
          </h3>
          <p style={{ color: '#64748b', fontSize: '13px', lineHeight: '1.6' }}>
            React is running inside your Chrome extension.
            The full chat UI arrives in Phase 5.
          </p>
        </div>
      )}
    </>
  );
};

export default App;
