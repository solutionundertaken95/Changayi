/**
 * ChatPanel.tsx
 *
 * The main chat UI component. Contains:
 *  - Header: page title, clear & close buttons
 *  - Empty state: clickable starter prompts
 *  - Message list: user bubbles (right) + AI bubbles (left)
 *  - Source cards: which chunks contributed to each AI answer
 *  - Typing indicator: polished 3-dot animation
 *  - Input area: textarea + send button
 *
 * All styles are inline or in a <style> tag so they work
 * inside the Shadow DOM without leaking to the host page.
 */

import React, { useState, useEffect, useRef, KeyboardEvent } from 'react';
import { indexingState } from '../store/indexingState';
import { sendMessage } from '../services/api';
import type { Message, Source } from '../types/index';

// ─────────────────────────────────────────────────────────────
// STARTER PROMPTS shown in the empty state
// ─────────────────────────────────────────────────────────────
const STARTER_PROMPTS = [
  { icon: '📋', text: 'Summarize this page' },
  { icon: '🔑', text: 'What are the key points?' },
  { icon: '🧠', text: 'Explain this like I\'m a beginner' },
  { icon: '❓', text: 'What is this page about?' },
  { icon: '💡', text: 'Find the most important information' },
];

// ─────────────────────────────────────────────────────────────
// CSS injected into the Shadow DOM for animations and
// pseudo-element styles that can't be done with inline styles
// ─────────────────────────────────────────────────────────────
const CHAT_STYLES = `
  @keyframes ragSlideIn {
    from { opacity: 0; transform: translateY(20px) scale(0.97); }
    to   { opacity: 1; transform: translateY(0)    scale(1);    }
  }
  @keyframes ragFadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0);   }
  }
  @keyframes ragDotBounce {
    0%, 80%, 100% { transform: translateY(0);    opacity: 0.4; }
    40%           { transform: translateY(-6px); opacity: 1;   }
  }
  @keyframes ragPulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.5; }
  }
  @keyframes ragSpin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
  }

  .rag-panel {
    animation: ragSlideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }
  .rag-msg {
    animation: ragFadeIn 0.2s ease forwards;
  }

  /* Scrollbar styling inside messages area */
  .rag-messages::-webkit-scrollbar { width: 4px; }
  .rag-messages::-webkit-scrollbar-track { background: transparent; }
  .rag-messages::-webkit-scrollbar-thumb {
    background: rgba(99, 102, 241, 0.25);
    border-radius: 4px;
  }

  /* Input focus ring */
  .rag-input:focus {
    outline: none;
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
  }

  /* Send button hover */
  .rag-send:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  }
  .rag-send:active:not(:disabled) { transform: scale(0.97); }
  .rag-send:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Starter prompt card hover */
  .rag-prompt:hover {
    background: #ede9fe !important;
    border-color: #6366f1 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.12);
  }
  .rag-prompt:active { transform: translateY(0); }

  /* Copy button hover */
  .rag-copy:hover { background: rgba(99,102,241,0.1) !important; }

  /* Source pill hover */
  .rag-source:hover { background: #ede9fe !important; }

  /* Clear button hover */
  .rag-clear:hover { background: rgba(255,255,255,0.2) !important; }
  .rag-close-btn:hover { background: rgba(255,255,255,0.2) !important; }

  /* Typing dots */
  .rag-dot:nth-child(1) { animation: ragDotBounce 1.2s ease-in-out 0s   infinite; }
  .rag-dot:nth-child(2) { animation: ragDotBounce 1.2s ease-in-out 0.2s infinite; }
  .rag-dot:nth-child(3) { animation: ragDotBounce 1.2s ease-in-out 0.4s infinite; }

  /* Indexing spinner */
  .rag-spinner { animation: ragSpin 1s linear infinite; }

  /* Textarea resize handle */
  .rag-input { resize: none; }
`;

// ─────────────────────────────────────────────────────────────
// TYPING INDICATOR — 3 animated dots
// ─────────────────────────────────────────────────────────────
const TypingIndicator: React.FC = () => (
  <div className="rag-msg" style={{
    display: 'flex',
    alignItems: 'flex-end',
    gap: 8,
    marginBottom: 16,
  }}>
    {/* AI avatar */}
    <div style={{
      width: 28, height: 28,
      borderRadius: '50%',
      background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 14, flexShrink: 0,
    }}>🤖</div>

    {/* Bubble with bouncing dots */}
    <div style={{
      background: '#fff',
      border: '1px solid #e5e7eb',
      borderRadius: '18px 18px 18px 4px',
      padding: '12px 16px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      display: 'flex', alignItems: 'center', gap: 5,
    }}>
      <div className="rag-dot" style={{ width: 7, height: 7, borderRadius: '50%', background: '#6366f1' }} />
      <div className="rag-dot" style={{ width: 7, height: 7, borderRadius: '50%', background: '#6366f1' }} />
      <div className="rag-dot" style={{ width: 7, height: 7, borderRadius: '50%', background: '#6366f1' }} />
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// SOURCE CARDS — show which chunks contributed to the answer
// ─────────────────────────────────────────────────────────────
const SourceCards: React.FC<{ sources: Source[] }> = ({ sources }) => {
  if (!sources || sources.length === 0) return null;

  return (
    <div style={{ marginTop: 10 }}>
      <p style={{
        margin: '0 0 6px 0',
        fontSize: 11,
        fontWeight: 600,
        color: '#9ca3af',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
      }}>
        Sources
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {sources.map((src, i) => (
          <div
            key={i}
            className="rag-source"
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '4px 10px',
              background: '#f5f3ff',
              border: '1px solid #ddd6fe',
              borderRadius: 20,
              cursor: 'default',
              transition: 'background 0.15s',
            }}
            title={src.content ? src.content.slice(0, 150) + '…' : undefined}
          >
            <span style={{ fontSize: 12 }}>📄</span>
            <span style={{ fontSize: 11, color: '#6d28d9', fontWeight: 500 }}>
              Chunk {src.chunk_index + 1}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// MESSAGE BUBBLE — renders a single chat message
// ─────────────────────────────────────────────────────────────
const MessageBubble: React.FC<{ message: Message }> = ({ message }) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  const isError = message.role === 'error';

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ── User message ──────────────────────────────────────────
  if (isUser) {
    return (
      <div className="rag-msg" style={{
        display: 'flex',
        justifyContent: 'flex-end',
        marginBottom: 16,
      }}>
        <div style={{
          maxWidth: '78%',
          background: 'linear-gradient(135deg, #6366f1, #7c3aed)',
          color: '#fff',
          borderRadius: '18px 18px 4px 18px',
          padding: '12px 16px',
          fontSize: 14,
          lineHeight: 1.5,
          boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)',
          wordBreak: 'break-word',
        }}>
          {message.content}
        </div>
      </div>
    );
  }

  // ── Error message ─────────────────────────────────────────
  if (isError) {
    return (
      <div className="rag-msg" style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        marginBottom: 16,
      }}>
        <div style={{
          width: 28, height: 28,
          borderRadius: '50%',
          background: '#fee2e2',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, flexShrink: 0,
        }}>⚠️</div>
        <div style={{
          background: '#fef2f2',
          border: '1px solid #fca5a5',
          borderRadius: '18px 18px 18px 4px',
          padding: '12px 16px',
          color: '#dc2626',
          fontSize: 14,
          lineHeight: 1.5,
        }}>
          {message.content}
        </div>
      </div>
    );
  }

  // ── AI message ────────────────────────────────────────────
  return (
    <div className="rag-msg" style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 8,
      marginBottom: 16,
    }}>
      {/* AI avatar */}
      <div style={{
        width: 28, height: 28,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 14, flexShrink: 0, marginTop: 2,
      }}>🤖</div>

      {/* Message content */}
      <div style={{ maxWidth: '85%', flex: 1 }}>
        <div style={{
          background: '#fff',
          border: '1px solid #e5e7eb',
          borderRadius: '18px 18px 18px 4px',
          padding: '12px 16px',
          fontSize: 14,
          lineHeight: 1.6,
          color: '#111827',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          wordBreak: 'break-word',
          whiteSpace: 'pre-wrap',
        }}>
          {message.content}
        </div>

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <SourceCards sources={message.sources} />
        )}

        {/* Copy button */}
        <div style={{ marginTop: 6, display: 'flex', gap: 6 }}>
          <button
            className="rag-copy"
            onClick={handleCopy}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              fontSize: 11,
              color: '#9ca3af',
              padding: '3px 8px',
              borderRadius: 6,
              transition: 'background 0.15s',
              display: 'flex', alignItems: 'center', gap: 4,
            }}
          >
            {copied ? '✅ Copied' : '📋 Copy'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// EMPTY STATE — shown when no messages exist yet
// ─────────────────────────────────────────────────────────────
const EmptyState: React.FC<{ onPrompt: (text: string) => void; isReady: boolean }> = ({
  onPrompt,
  isReady,
}) => (
  <div style={{
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px 20px',
    gap: 20,
  }}>
    {/* Hero icon */}
    <div style={{
      width: 64, height: 64,
      borderRadius: '50%',
      background: 'linear-gradient(135deg, #ede9fe, #ddd6fe)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 30,
    }}>
      🤖
    </div>

    <div style={{ textAlign: 'center' }}>
      <p style={{ margin: '0 0 6px 0', fontSize: 16, fontWeight: 700, color: '#111827' }}>
        Ask me anything
      </p>
      <p style={{ margin: 0, fontSize: 13, color: '#6b7280', lineHeight: 1.5, maxWidth: 260 }}>
        {isReady
          ? 'I\'ve analyzed this page and I\'m ready to answer your questions.'
          : 'Analyzing the page… I\'ll be ready in a moment.'}
      </p>
    </div>

    {/* Starter prompts — only show when page is indexed */}
    {isReady && (
      <div style={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}>
        <p style={{
          margin: '0 0 4px 0',
          fontSize: 11,
          fontWeight: 600,
          color: '#9ca3af',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          textAlign: 'center',
        }}>
          Try asking
        </p>
        {STARTER_PROMPTS.map((prompt) => (
          <button
            key={prompt.text}
            className="rag-prompt"
            onClick={() => onPrompt(prompt.text)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              width: '100%',
              padding: '10px 14px',
              background: '#f9fafb',
              border: '1px solid #e5e7eb',
              borderRadius: 12,
              cursor: 'pointer',
              textAlign: 'left',
              fontSize: 13,
              color: '#374151',
              fontWeight: 500,
              transition: 'all 0.15s',
            }}
          >
            <span style={{ fontSize: 16 }}>{prompt.icon}</span>
            {prompt.text}
          </button>
        ))}
      </div>
    )}

    {/* Spinner when indexing */}
    {!isReady && (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div className="rag-spinner" style={{
          width: 16, height: 16,
          border: '2px solid #e5e7eb',
          borderTopColor: '#6366f1',
          borderRadius: '50%',
        }} />
        <span style={{ fontSize: 13, color: '#9ca3af' }}>Analyzing page content…</span>
      </div>
    )}
  </div>
);

// ─────────────────────────────────────────────────────────────
// CHAT PANEL — the main component exported from this file
// ─────────────────────────────────────────────────────────────
interface ChatPanelProps {
  onClose: () => void;
}

const ChatPanel: React.FC<ChatPanelProps> = ({ onClose }) => {
  // ── State ───────────────────────────────────────────────────
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [pageState, setPageState] = useState(indexingState.getState());

  // ── Refs ────────────────────────────────────────────────────
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Subscribe to page indexing state ────────────────────────
  useEffect(() => {
    // Subscribe returns an unsubscribe function — clean up on unmount
    const unsubscribe = indexingState.subscribe((newState) => {
      setPageState(newState);
    });
    return unsubscribe;
  }, []);

  // ── Auto-scroll messages to bottom ──────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // ── Focus input on open ─────────────────────────────────────
  useEffect(() => {
    if (pageState.status === 'ready') {
      inputRef.current?.focus();
    }
  }, [pageState.status]);

  // ── Send message handler ─────────────────────────────────────
  const handleSend = async (overrideText?: string) => {
    const question = overrideText ?? input.trim();
    if (!question || isLoading || pageState.status !== 'ready') return;

    // 1. Add the user's message to the list immediately
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    // 2. Call the RAG backend
    try {
      const response = await sendMessage({
        session_id: pageState.sessionId!,
        question,
      });

      // 3. Add the AI's response
      const aiMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
        sources: response.sources,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      // 4. Show an error bubble if something went wrong
      const errMsg: Message = {
        id: crypto.randomUUID(),
        role: 'error',
        content: 'Something went wrong. Make sure the backend is running and try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
      // Re-focus input after response
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  // ── Keyboard handler — Enter to send, Shift+Enter for newline ─
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Auto-resize textarea as user types ───────────────────────
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Reset height then set to scrollHeight to grow with content
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  const isReady = pageState.status === 'ready';
  const canSend = isReady && input.trim().length > 0 && !isLoading;

  // ── Truncate long page titles for the header ──────────────────
  const pageTitle = pageState.pageTitle
    ? pageState.pageTitle.length > 40
      ? pageState.pageTitle.slice(0, 37) + '…'
      : pageState.pageTitle
    : 'Current Page';

  // ─────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────
  return (
    <>
      {/* Inject animation styles into Shadow DOM */}
      <style>{CHAT_STYLES}</style>

      <div
        className="rag-panel"
        style={{
          position: 'fixed',
          bottom: 88,
          right: 20,
          width: 380,
          height: 580,
          background: '#f9fafb',
          borderRadius: 20,
          boxShadow: '0 24px 64px rgba(0,0,0,0.18), 0 4px 16px rgba(0,0,0,0.08)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          zIndex: 2147483646,
          pointerEvents: 'auto',
          border: '1px solid rgba(99,102,241,0.15)',
        }}
      >
        {/* ── HEADER ────────────────────────────────────────── */}
        <div style={{
          background: 'linear-gradient(135deg, #6366f1 0%, #7c3aed 100%)',
          padding: '14px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          flexShrink: 0,
        }}>
          {/* Top row: identity + controls */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 32, height: 32,
                borderRadius: '50%',
                background: 'rgba(255,255,255,0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 16,
              }}>🤖</div>
              <div>
                <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#fff' }}>
                  Page Assistant
                </p>
                <p style={{ margin: 0, fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
                  Powered by Gemini
                </p>
              </div>
            </div>

            {/* Controls: clear + close */}
            <div style={{ display: 'flex', gap: 6 }}>
              {messages.length > 0 && (
                <button
                  className="rag-clear"
                  onClick={() => setMessages([])}
                  title="Clear conversation"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'rgba(255,255,255,0.85)',
                    fontSize: 14,
                    padding: '4px 8px',
                    borderRadius: 8,
                    transition: 'background 0.15s',
                  }}
                >
                  🗑️
                </button>
              )}
              <button
                className="rag-close-btn"
                onClick={onClose}
                title="Close"
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'rgba(255,255,255,0.85)',
                  fontSize: 18,
                  lineHeight: 1,
                  padding: '4px 6px',
                  borderRadius: 8,
                  transition: 'background 0.15s',
                }}
              >
                ✕
              </button>
            </div>
          </div>

          {/* Page context badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(255,255,255,0.15)',
            borderRadius: 8,
            padding: '5px 10px',
          }}>
            <span style={{ fontSize: 12 }}>
              {isReady ? '✅' : pageState.status === 'indexing' ? '⏳' : '⚠️'}
            </span>
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.9)', fontWeight: 500 }}>
              {isReady ? pageTitle : pageState.message || 'Loading…'}
            </span>
          </div>
        </div>

        {/* ── MESSAGES AREA ─────────────────────────────────── */}
        <div
          className="rag-messages"
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: messages.length === 0 ? 0 : '16px 16px 0 16px',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Empty state */}
          {messages.length === 0 && !isLoading && (
            <EmptyState onPrompt={handleSend} isReady={isReady} />
          )}

          {/* Message list */}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Typing indicator while waiting for AI */}
          {isLoading && <TypingIndicator />}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} style={{ height: 16 }} />
        </div>

        {/* ── INPUT AREA ────────────────────────────────────── */}
        <div style={{
          padding: '12px 14px',
          borderTop: '1px solid #e5e7eb',
          background: '#fff',
          flexShrink: 0,
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: 10,
            background: '#f9fafb',
            borderRadius: 14,
            border: '1.5px solid #e5e7eb',
            padding: '8px 10px 8px 14px',
            transition: 'border-color 0.2s, box-shadow 0.2s',
          }}>
            <textarea
              ref={inputRef}
              className="rag-input"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={
                isReady
                  ? 'Ask about this page… (Enter to send)'
                  : 'Analyzing page, please wait…'
              }
              disabled={!isReady || isLoading}
              rows={1}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                fontSize: 14,
                color: '#111827',
                lineHeight: 1.5,
                fontFamily: 'inherit',
                overflowY: 'hidden',
                minHeight: 22,
                maxHeight: 120,
                paddingTop: 2,
              }}
            />

            {/* Send button */}
            <button
              className="rag-send"
              onClick={() => handleSend()}
              disabled={!canSend}
              title="Send (Enter)"
              style={{
                width: 36, height: 36,
                borderRadius: 10,
                background: canSend
                  ? 'linear-gradient(135deg, #6366f1, #7c3aed)'
                  : '#e5e7eb',
                border: 'none',
                cursor: canSend ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 16,
                transition: 'all 0.15s',
                flexShrink: 0,
              }}
            >
              {isLoading
                ? <div className="rag-spinner" style={{
                    width: 16, height: 16,
                    border: '2px solid rgba(255,255,255,0.4)',
                    borderTopColor: '#fff',
                    borderRadius: '50%',
                  }} />
                : <span style={{ color: canSend ? '#fff' : '#9ca3af' }}>↑</span>
              }
            </button>
          </div>

          {/* Hint text */}
          <p style={{
            margin: '6px 2px 0',
            fontSize: 11,
            color: '#9ca3af',
            textAlign: 'center',
          }}>
            Shift+Enter for new line · Answers grounded in page content
          </p>
        </div>
      </div>
    </>
  );
};

export default ChatPanel;
