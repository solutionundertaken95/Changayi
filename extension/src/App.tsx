/**
 * App.tsx — Root React component for the chatbot
 *
 * Phase 1: This is a minimal placeholder.
 * It renders a floating button that proves React is working inside the page.
 *
 * In Phase 5 (Chat UI), this will become:
 *   - A floating "✨ Ask AI" pill button
 *   - A full chat panel with messages, input, loading states
 *   - Source references, dark mode, etc.
 *
 * For now: if you see the button on a webpage, the extension is working.
 */

import React, { useState } from 'react';

const App: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Floating button — always visible */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          zIndex: 2147483647,       // Maximum z-index — always on top
          background: '#6366f1',
          color: '#fff',
          border: 'none',
          borderRadius: '50px',
          padding: '12px 20px',
          fontSize: '14px',
          fontWeight: '600',
          cursor: 'pointer',
          boxShadow: '0 4px 20px rgba(99, 102, 241, 0.4)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          transition: 'transform 0.2s, box-shadow 0.2s',
        }}
      >
        ✨ Scene Inda?
      </button>

      {/* Placeholder panel — Phase 5 will replace this with the full UI */}
      {isOpen && (
        <div
          style={{
            position: 'fixed',
            bottom: '80px',
            right: '24px',
            width: '360px',
            background: '#fff',
            borderRadius: '16px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
            padding: '24px',
            zIndex: 2147483646,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          }}
        >
          <h3 style={{ marginBottom: '8px', color: '#1e293b' }}>
            🎉 Phase 1 Complete!
          </h3>
          <p style={{ color: '#64748b', fontSize: '13px' }}>
            React is running inside your Chrome extension.
            The full chat UI is coming in Phase 5.
          </p>
        </div>
      )}
    </>
  );
};

export default App;
