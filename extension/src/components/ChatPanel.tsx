/**
 * ChatPanel.tsx — Phase 7+8
 *
 * The main chat UI component. Contains:
 *  - Header: page title, dark mode toggle, clear & close buttons
 *  - Empty state: clickable starter prompts
 *  - Message list: user bubbles (right) + AI bubbles (left)
 *  - MarkdownContent: renders bold, italic, code, lists, headings in AI responses
 *  - Source cards: which chunks contributed to each AI answer
 *  - Typing indicator: polished 3-dot animation (while waiting for first chunk)
 *  - Input area: textarea + send button
 *
 * Phase 7 additions: dark mode toggle + markdown rendering in AI messages
 * Phase 8 addition:  streaming handleSend via sendMessageStream (SSE)
 *
 * All styles are inline or in a <style> tag so they work
 * inside the Shadow DOM without leaking to the host page.
 */

import React, { useState, useEffect, useRef, KeyboardEvent } from 'react';
import { indexingState } from '../store/indexingState';
import { sendMessageStream } from '../services/api';
import type { Message, Source } from '../types/index';

// ─────────────────────────────────────────────────────────────
// STARTER PROMPTS shown in the empty state
// ─────────────────────────────────────────────────────────────
const STARTER_PROMPTS = [
  { icon: '📋', text: 'Summarize this page' },
  { icon: '🔑', text: 'What are the key points?' },
  { icon: '🧠', text: "Explain this like I'm a beginner" },
  { icon: '❓', text: 'What is this page about?' },
  { icon: '💡', text: 'Find the most important information' },
];

// ─────────────────────────────────────────────────────────────
// DARK / LIGHT THEME TOKENS
// ─────────────────────────────────────────────────────────────
function buildTheme(dark: boolean) {
  return {
    panelBg:          dark ? '#0d0d1a' : '#f9fafb',
    panelBorder:      dark ? 'rgba(99,102,241,0.35)' : 'rgba(99,102,241,0.15)',
    msgBg:            dark ? '#1a1a2e' : '#ffffff',
    msgBorder:        dark ? '#2d2d45' : '#e5e7eb',
    msgText:          dark ? '#e2e8f0' : '#111827',
    inputAreaBg:      dark ? '#0a0a16' : '#ffffff',
    inputWrapBg:      dark ? '#1a1a2e' : '#f9fafb',
    inputWrapBorder:  dark ? '#2d2d45' : '#e5e7eb',
    inputText:        dark ? '#e2e8f0' : '#111827',
    inputPlaceholder: dark ? '#6b7280' : '#9ca3af',
    hintText:         dark ? '#4b5563' : '#9ca3af',
    sourcePillBg:     dark ? '#1f1b3a' : '#f5f3ff',
    sourcePillBorder: dark ? '#4c1d95' : '#ddd6fe',
    sourceText:       dark ? '#a78bfa' : '#6d28d9',
    sourceLabelColor: dark ? '#6b7280' : '#9ca3af',
    promptBg:         dark ? '#1a1a2e' : '#f9fafb',
    promptBorder:     dark ? '#2d2d45' : '#e5e7eb',
    promptText:       dark ? '#d1d5db' : '#374151',
    heroCircleBg:     dark ? 'linear-gradient(135deg,#2d2b55,#1e1b3a)' : 'linear-gradient(135deg,#ede9fe,#ddd6fe)',
    emptyTitle:       dark ? '#e2e8f0' : '#111827',
    emptySubtitle:    dark ? '#9ca3af' : '#6b7280',
    codeBlockBg:      dark ? '#0a0a16' : '#1e1e2e',
    codeBlockText:    dark ? '#d4d4d8' : '#d4d4d8',
    inlineCodeBg:     dark ? 'rgba(99,102,241,0.2)' : 'rgba(99,102,241,0.1)',
    scrollThumb:      dark ? 'rgba(99,102,241,0.4)' : 'rgba(99,102,241,0.25)',
    dotBg:            dark ? '#818cf8' : '#6366f1',
    ctxBg:            dark ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.15)',
    ctxText:          dark ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.9)',
  };
}

// ─────────────────────────────────────────────────────────────
// CSS injected into the Shadow DOM
// ─────────────────────────────────────────────────────────────
const buildStyles = (dark: boolean, st: ReturnType<typeof buildTheme>) => `
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
  @keyframes ragSpin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
  }

  .rag-panel { animation: ragSlideIn 0.25s cubic-bezier(0.16,1,0.3,1) forwards; }
  .rag-msg   { animation: ragFadeIn  0.2s ease forwards; }

  .rag-messages::-webkit-scrollbar       { width: 4px; }
  .rag-messages::-webkit-scrollbar-track { background: transparent; }
  .rag-messages::-webkit-scrollbar-thumb {
    background: ${st.scrollThumb};
    border-radius: 4px;
  }

  .rag-input:focus {
    outline: none;
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
  }

  .rag-send:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(99,102,241,0.4);
  }
  .rag-send:active:not(:disabled) { transform: scale(0.97); }
  .rag-send:disabled { opacity: 0.5; cursor: not-allowed; }

  .rag-prompt:hover {
    background: ${dark ? '#2d2b55' : '#ede9fe'} !important;
    border-color: #6366f1 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99,102,241,0.12);
  }
  .rag-prompt:active { transform: translateY(0); }

  .rag-copy:hover   { background: rgba(99,102,241,0.1) !important; }
  .rag-source:hover { background: ${dark ? '#2d2b55' : '#ede9fe'} !important; }
  .rag-clear:hover  { background: rgba(255,255,255,0.2) !important; }
  .rag-close-btn:hover { background: rgba(255,255,255,0.2) !important; }
  .rag-dark-btn:hover  { background: rgba(255,255,255,0.2) !important; }

  .rag-dot:nth-child(1) { animation: ragDotBounce 1.2s ease-in-out 0s   infinite; }
  .rag-dot:nth-child(2) { animation: ragDotBounce 1.2s ease-in-out 0.2s infinite; }
  .rag-dot:nth-child(3) { animation: ragDotBounce 1.2s ease-in-out 0.4s infinite; }

  .rag-spinner { animation: ragSpin 1s linear infinite; }
  .rag-input   { resize: none; }
`;

// ─────────────────────────────────────────────────────────────
// INLINE MARKDOWN PARSER — returns React nodes for bold/italic/code
// ─────────────────────────────────────────────────────────────
function parseInline(text: string, theme: ReturnType<typeof buildTheme>): React.ReactNode {
  // Regex matches **bold**, *italic*, `inline code`
  const regex = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`)/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[0].startsWith('**')) {
      parts.push(<strong key={key++} style={{ fontWeight: 700 }}>{match[2]}</strong>);
    } else if (match[0].startsWith('*')) {
      parts.push(<em key={key++}>{match[3]}</em>);
    } else {
      // inline code
      parts.push(
        <code key={key++} style={{
          background: theme.inlineCodeBg,
          color: '#818cf8',
          borderRadius: 4,
          padding: '1px 5px',
          fontFamily: 'ui-monospace, SFMono-Regular, monospace',
          fontSize: '0.88em',
        }}>
          {match[4]}
        </code>
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length === 0 ? '' : parts.length === 1 ? parts[0] : <>{parts}</>;
}

// ─────────────────────────────────────────────────────────────
// MARKDOWN CONTENT — block-level markdown renderer
// ─────────────────────────────────────────────────────────────
const MarkdownContent: React.FC<{ content: string; theme: ReturnType<typeof buildTheme> }> = ({
  content,
  theme,
}) => {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;
  let keyCounter = 0;
  const k = () => keyCounter++;

  while (i < lines.length) {
    const line = lines[i];

    // ── Fenced code block ─────────────────────────────────
    if (line.startsWith('```')) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      elements.push(
        <pre key={k()} style={{
          background: theme.codeBlockBg,
          color: theme.codeBlockText,
          borderRadius: 8,
          padding: '12px 14px',
          overflowX: 'auto',
          fontSize: 12.5,
          margin: '8px 0',
          fontFamily: 'ui-monospace, SFMono-Regular, monospace',
          lineHeight: 1.55,
          border: '1px solid rgba(99,102,241,0.2)',
        }}>
          <code>{codeLines.join('\n')}</code>
        </pre>
      );
      i++; // skip closing ```
      continue;
    }

    // ── Headings ──────────────────────────────────────────
    if (line.startsWith('### ')) {
      elements.push(
        <p key={k()} style={{ fontWeight: 700, fontSize: 14, margin: '10px 0 3px', color: theme.msgText }}>
          {parseInline(line.slice(4), theme)}
        </p>
      );
      i++; continue;
    }
    if (line.startsWith('## ')) {
      elements.push(
        <p key={k()} style={{ fontWeight: 700, fontSize: 15, margin: '12px 0 4px', color: theme.msgText }}>
          {parseInline(line.slice(3), theme)}
        </p>
      );
      i++; continue;
    }
    if (line.startsWith('# ')) {
      elements.push(
        <p key={k()} style={{ fontWeight: 700, fontSize: 16, margin: '14px 0 5px', color: theme.msgText }}>
          {parseInline(line.slice(2), theme)}
        </p>
      );
      i++; continue;
    }

    // ── Bullet list ───────────────────────────────────────
    if (line.startsWith('- ') || line.startsWith('* ')) {
      elements.push(
        <div key={k()} style={{ display: 'flex', gap: 8, margin: '3px 0', color: theme.msgText }}>
          <span style={{ color: '#818cf8', flexShrink: 0, lineHeight: 1.6 }}>•</span>
          <span style={{ lineHeight: 1.6 }}>{parseInline(line.slice(2), theme)}</span>
        </div>
      );
      i++; continue;
    }

    // ── Numbered list ─────────────────────────────────────
    const numMatch = line.match(/^(\d+)\.\s(.*)$/);
    if (numMatch) {
      elements.push(
        <div key={k()} style={{ display: 'flex', gap: 8, margin: '3px 0', color: theme.msgText }}>
          <span style={{ color: '#818cf8', flexShrink: 0, fontWeight: 600, lineHeight: 1.6, minWidth: 16 }}>
            {numMatch[1]}.
          </span>
          <span style={{ lineHeight: 1.6 }}>{parseInline(numMatch[2], theme)}</span>
        </div>
      );
      i++; continue;
    }

    // ── Horizontal rule ───────────────────────────────────
    if (line.trim() === '---' || line.trim() === '***') {
      elements.push(
        <hr key={k()} style={{ border: 'none', borderTop: `1px solid ${theme.msgBorder}`, margin: '10px 0' }} />
      );
      i++; continue;
    }

    // ── Empty line → vertical spacing ────────────────────
    if (line.trim() === '') {
      elements.push(<div key={k()} style={{ height: 6 }} />);
      i++; continue;
    }

    // ── Regular paragraph ─────────────────────────────────
    elements.push(
      <p key={k()} style={{ margin: '3px 0', lineHeight: 1.65, color: theme.msgText }}>
        {parseInline(line, theme)}
      </p>
    );
    i++;
  }

  return <div style={{ fontSize: 14, wordBreak: 'break-word' }}>{elements}</div>;
};

// ─────────────────────────────────────────────────────────────
// TYPING INDICATOR — 3 animated dots
// ─────────────────────────────────────────────────────────────
const TypingIndicator: React.FC<{ dotColor: string }> = ({ dotColor }) => (
  <div className="rag-msg" style={{ display: 'flex', alignItems: 'flex-end', gap: 8, marginBottom: 16 }}>
    <div style={{
      width: 28, height: 28,
      borderRadius: '50%',
      background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 14, flexShrink: 0,
    }}>🤖</div>
    <div style={{
      background: 'linear-gradient(135deg, #f8f7ff, #ede9fe)',
      border: '1px solid #ddd6fe',
      borderRadius: '18px 18px 18px 4px',
      padding: '12px 16px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      display: 'flex', alignItems: 'center', gap: 5,
    }}>
      <div className="rag-dot" style={{ width: 7, height: 7, borderRadius: '50%', background: dotColor }} />
      <div className="rag-dot" style={{ width: 7, height: 7, borderRadius: '50%', background: dotColor }} />
      <div className="rag-dot" style={{ width: 7, height: 7, borderRadius: '50%', background: dotColor }} />
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// SOURCE CARDS
// ─────────────────────────────────────────────────────────────
const SourceCards: React.FC<{ sources: Source[]; theme: ReturnType<typeof buildTheme> }> = ({
  sources,
  theme,
}) => {
  if (!sources || sources.length === 0) return null;
  return (
    <div style={{ marginTop: 10 }}>
      <p style={{
        margin: '0 0 6px 0',
        fontSize: 11,
        fontWeight: 600,
        color: theme.sourceLabelColor,
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
              background: theme.sourcePillBg,
              border: `1px solid ${theme.sourcePillBorder}`,
              borderRadius: 20,
              cursor: 'default',
              transition: 'background 0.15s',
            }}
            title={src.content ? src.content.slice(0, 150) + '…' : undefined}
          >
            <span style={{ fontSize: 12 }}>📄</span>
            <span style={{ fontSize: 11, color: theme.sourceText, fontWeight: 500 }}>
              Chunk {src.chunk_index + 1}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// MESSAGE BUBBLE
// ─────────────────────────────────────────────────────────────
interface MessageBubbleProps {
  message: Message;
  theme: ReturnType<typeof buildTheme>;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, theme }) => {
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
      <div className="rag-msg" style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <div style={{
          maxWidth: '78%',
          background: 'linear-gradient(135deg, #6366f1, #7c3aed)',
          color: '#fff',
          borderRadius: '18px 18px 4px 18px',
          padding: '12px 16px',
          fontSize: 14,
          lineHeight: 1.5,
          boxShadow: '0 4px 12px rgba(99,102,241,0.3)',
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
      <div className="rag-msg" style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 16 }}>
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

  // ── AI message (streaming-aware + markdown) ───────────────
  const isEmpty = !message.content;

  return (
    <div className="rag-msg" style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 16 }}>
      {/* Avatar */}
      <div style={{
        width: 28, height: 28,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 14, flexShrink: 0, marginTop: 2,
      }}>🤖</div>

      <div style={{ maxWidth: '85%', flex: 1 }}>
        <div style={{
          background: theme.msgBg,
          border: `1px solid ${theme.msgBorder}`,
          borderRadius: '18px 18px 18px 4px',
          padding: '12px 16px',
          fontSize: 14,
          lineHeight: 1.6,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          minHeight: 44,
          position: 'relative',
        }}>
          {isEmpty ? (
            /* Streaming hasn't started yet — show a subtle pulse */
            <div style={{ display: 'flex', gap: 4, alignItems: 'center', padding: '2px 0' }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#818cf8',
                animation: 'ragDotBounce 1.2s ease-in-out 0s infinite',
              }} />
            </div>
          ) : (
            <MarkdownContent content={message.content} theme={theme} />
          )}
        </div>

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <SourceCards sources={message.sources} theme={theme} />
        )}

        {/* Copy button (only when there's content) */}
        {!isEmpty && (
          <div style={{ marginTop: 6, display: 'flex', gap: 6 }}>
            <button
              className="rag-copy"
              onClick={handleCopy}
              style={{
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontSize: 11,
                color: theme.hintText,
                padding: '3px 8px',
                borderRadius: 6,
                transition: 'background 0.15s',
                display: 'flex', alignItems: 'center', gap: 4,
              }}
            >
              {copied ? '✅ Copied' : '📋 Copy'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// EMPTY STATE
// ─────────────────────────────────────────────────────────────
interface EmptyStateProps {
  onPrompt: (text: string) => void;
  isReady: boolean;
  theme: ReturnType<typeof buildTheme>;
}

const EmptyState: React.FC<EmptyStateProps> = ({ onPrompt, isReady, theme }) => (
  <div style={{
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px 20px',
    gap: 20,
  }}>
    <div style={{
      width: 64, height: 64,
      borderRadius: '50%',
      background: theme.heroCircleBg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 30,
    }}>
      🤖
    </div>

    <div style={{ textAlign: 'center' }}>
      <p style={{ margin: '0 0 6px 0', fontSize: 16, fontWeight: 700, color: theme.emptyTitle }}>
        Ask me anything
      </p>
      <p style={{ margin: 0, fontSize: 13, color: theme.emptySubtitle, lineHeight: 1.5, maxWidth: 260 }}>
        {isReady
          ? "I've analyzed this page and I'm ready to answer your questions."
          : 'Analyzing the page… I\'ll be ready in a moment.'}
      </p>
    </div>

    {isReady && (
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <p style={{
          margin: '0 0 4px 0',
          fontSize: 11,
          fontWeight: 600,
          color: theme.sourceLabelColor,
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
              background: theme.promptBg,
              border: `1px solid ${theme.promptBorder}`,
              borderRadius: 12,
              cursor: 'pointer',
              textAlign: 'left',
              fontSize: 13,
              color: theme.promptText,
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

    {!isReady && (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div className="rag-spinner" style={{
          width: 16, height: 16,
          border: '2px solid #e5e7eb',
          borderTopColor: '#6366f1',
          borderRadius: '50%',
        }} />
        <span style={{ fontSize: 13, color: theme.emptySubtitle }}>Analyzing page content…</span>
      </div>
    )}
  </div>
);

// ─────────────────────────────────────────────────────────────
// CHAT PANEL — main exported component
// ─────────────────────────────────────────────────────────────
interface ChatPanelProps {
  onClose: () => void;
}

const ChatPanel: React.FC<ChatPanelProps> = ({ onClose }) => {
  // ── State ───────────────────────────────────────────────────
  const [messages, setMessages]   = useState<Message[]>([]);
  const [input, setInput]         = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [darkMode, setDarkMode]   = useState(false);
  const [pageState, setPageState] = useState(indexingState.getState());

  const theme = buildTheme(darkMode);

  // ── Refs ────────────────────────────────────────────────────
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef       = useRef<HTMLTextAreaElement>(null);

  // ── Subscribe to page indexing state ────────────────────────
  useEffect(() => {
    const unsubscribe = indexingState.subscribe((newState) => {
      setPageState(newState);
    });
    return unsubscribe;
  }, []);

  // ── Clear messages when navigating to a new page (SPA) ──────
  useEffect(() => {
    if (pageState.sessionId) {
      setMessages([]);
      setInput('');
      setIsLoading(false);
    }
  }, [pageState.sessionId]);

  // ── Auto-scroll to bottom ───────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // ── Focus input when ready ──────────────────────────────────
  useEffect(() => {
    if (pageState.status === 'ready') {
      inputRef.current?.focus();
    }
  }, [pageState.status]);

  // ── Send message (Phase 8 — streaming) ──────────────────────
  //
  // How streaming works:
  //   1. Add user message to chat immediately (instant feedback)
  //   2. Add an empty AI message as a placeholder
  //   3. Open SSE stream to /api/chat/stream
  //   4. onSources: attach retrieved chunks to the AI message
  //   5. onChunk: append each Gemini token to the AI message content
  //   6. onDone: set isLoading=false, re-focus input
  //   7. onError: replace placeholder with an error message
  //
  //  The user sees the answer appear progressively rather than waiting.
  // ─────────────────────────────────────────────────────────────
  const handleSend = async (overrideText?: string) => {
    const question = overrideText ?? input.trim();
    if (!question || isLoading || pageState.status !== 'ready') return;

    // 1. Add user message
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    // 2. Add an empty placeholder for the AI response
    //    (content starts empty and grows as chunks arrive)
    const aiMsgId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: aiMsgId, role: 'assistant', content: '', timestamp: new Date(), sources: [] },
    ]);

    // 3. Open SSE stream
    try {
      await sendMessageStream(
        { session_id: pageState.sessionId!, question },

        // onChunk — append token to the AI bubble
        (text) => {
          setMessages((prev) =>
            prev.map((m) => m.id === aiMsgId ? { ...m, content: m.content + text } : m)
          );
        },

        // onSources — attach source cards to the AI bubble
        (sources) => {
          setMessages((prev) =>
            prev.map((m) => m.id === aiMsgId ? { ...m, sources } : m)
          );
        },

        // onDone — streaming finished
        () => {
          setIsLoading(false);
          setTimeout(() => inputRef.current?.focus(), 100);
        },

        // onError — replace placeholder with error message
        (_err) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? {
                    ...m,
                    role: 'error' as const,
                    content: 'Something went wrong. Make sure the backend is running and try again.',
                  }
                : m
            )
          );
          setIsLoading(false);
          setTimeout(() => inputRef.current?.focus(), 100);
        },
      );
    } catch (_err) {
      // Fallback for any uncaught error from sendMessageStream itself
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId
            ? {
                ...m,
                role: 'error' as const,
                content: 'Something went wrong. Make sure the backend is running and try again.',
              }
            : m
        )
      );
      setIsLoading(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  // ── Keyboard: Enter = send, Shift+Enter = newline ────────────
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  // ── Auto-resize textarea ─────────────────────────────────────
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  const isReady = pageState.status === 'ready';
  const canSend = isReady && input.trim().length > 0 && !isLoading;

  const pageTitle = pageState.pageTitle
    ? pageState.pageTitle.length > 40
      ? pageState.pageTitle.slice(0, 37) + '…'
      : pageState.pageTitle
    : 'Current Page';

  // ── Show typing indicator only while waiting for first chunk ─
  // Once the AI message placeholder is added (content may be ''),
  // the TypingIndicator is replaced by the progressively-filling bubble.
  // We detect this by checking if the last message is already 'assistant'.
  const lastMsg = messages[messages.length - 1];
  const showTyping = isLoading && (!lastMsg || lastMsg.role === 'user');

  // ─────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────
  return (
    <>
      {/* Inject animation/hover styles into Shadow DOM */}
      <style>{buildStyles(darkMode, theme)}</style>

      <div
        className="rag-panel"
        style={{
          position: 'fixed',
          bottom: 88,
          right: 20,
          width: 380,
          height: 580,
          background: theme.panelBg,
          borderRadius: 20,
          boxShadow: darkMode
            ? '0 24px 64px rgba(0,0,0,0.6), 0 4px 16px rgba(0,0,0,0.4)'
            : '0 24px 64px rgba(0,0,0,0.18), 0 4px 16px rgba(0,0,0,0.08)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          zIndex: 2147483646,
          pointerEvents: 'auto',
          border: `1px solid ${theme.panelBorder}`,
          transition: 'background 0.2s, border-color 0.2s, box-shadow 0.2s',
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
          {/* Top row */}
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

            {/* Controls */}
            <div style={{ display: 'flex', gap: 6 }}>
              {/* Dark mode toggle — Phase 7 */}
              <button
                className="rag-dark-btn"
                onClick={() => setDarkMode((d) => !d)}
                title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'rgba(255,255,255,0.85)',
                  fontSize: 15,
                  padding: '4px 8px',
                  borderRadius: 8,
                  transition: 'background 0.15s',
                  lineHeight: 1,
                }}
              >
                {darkMode ? '☀️' : '🌙'}
              </button>

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
            background: theme.ctxBg,
            borderRadius: 8,
            padding: '5px 10px',
          }}>
            <span style={{ fontSize: 12 }}>
              {isReady ? '✅' : pageState.status === 'indexing' ? '⏳' : '⚠️'}
            </span>
            <span style={{ fontSize: 12, color: theme.ctxText, fontWeight: 500 }}>
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
            background: theme.panelBg,
            transition: 'background 0.2s',
          }}
        >
          {/* Empty state */}
          {messages.length === 0 && !isLoading && (
            <EmptyState onPrompt={(t) => void handleSend(t)} isReady={isReady} theme={theme} />
          )}

          {/* Message list */}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} theme={theme} />
          ))}

          {/* Typing indicator — only while waiting for first streaming chunk */}
          {showTyping && <TypingIndicator dotColor={theme.dotBg} />}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} style={{ height: 16 }} />
        </div>

        {/* ── INPUT AREA ────────────────────────────────────── */}
        <div style={{
          padding: '12px 14px',
          borderTop: `1px solid ${theme.msgBorder}`,
          background: theme.inputAreaBg,
          flexShrink: 0,
          transition: 'background 0.2s, border-color 0.2s',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: 10,
            background: theme.inputWrapBg,
            borderRadius: 14,
            border: `1.5px solid ${theme.inputWrapBorder}`,
            padding: '8px 10px 8px 14px',
            transition: 'border-color 0.2s, background 0.2s',
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
                color: theme.inputText,
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
              onClick={() => void handleSend()}
              disabled={!canSend}
              title="Send (Enter)"
              style={{
                width: 36, height: 36,
                borderRadius: 10,
                background: canSend
                  ? 'linear-gradient(135deg, #6366f1, #7c3aed)'
                  : darkMode ? '#1e1e30' : '#e5e7eb',
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
                : <span style={{ color: canSend ? '#fff' : darkMode ? '#4b5563' : '#9ca3af' }}>↑</span>
              }
            </button>
          </div>

          {/* Hint */}
          <p style={{
            margin: '6px 2px 0',
            fontSize: 11,
            color: theme.hintText,
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
