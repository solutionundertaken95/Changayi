/**
 * WorkspacePicker.tsx — Multi-Tab Knowledge Base UI.
 *
 * A dropdown in the chat panel header area that controls the retrieval scope:
 *
 *   "Current page"           → questions answer from this tab only
 *   "<workspace name> (N)"   → questions answer across every page in the KB
 *
 * Plus an "Add this page to KB" button which:
 *   1. Ensures the current page is indexed (on-demand — never automatic)
 *   2. Registers it into the selected workspace via /workspace/add_page
 *
 * Pages are NEVER added automatically. This button is the only path in.
 */

import React, { useState, useEffect } from 'react';
import { workspaceState } from '../store/workspaceState';
import { indexingState } from '../store/indexingState';
import {
  createWorkspace,
  addPageToWorkspace,
} from '../services/api';
import type { Workspace } from '../types';

interface PickerProps {
  theme: Record<string, string>;
}

const WorkspacePicker: React.FC<PickerProps> = ({ theme }) => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [adding, setAdding] = useState(false);
  const [addedMsg, setAddedMsg] = useState<string | null>(null);
  const [pageState, setPageState] = useState(indexingState.getState());

  useEffect(() => {
    const unsubWs = workspaceState.subscribe((id, list) => {
      setActiveId(id);
      setWorkspaces(list);
    });
    const unsubIdx = indexingState.subscribe(setPageState);
    void workspaceState.load();
    return () => {
      unsubWs();
      unsubIdx();
    };
  }, []);

  const active = workspaces.find((w) => w.workspace_id === activeId) ?? null;
  const isReady = pageState.status === 'ready';
  const isIndexing = pageState.status === 'indexing';

  /** Index (if needed) + register current page into the selected workspace. */
  const handleAddToKb = async () => {
    if (adding) return;
    setAdding(true);
    setAddedMsg(null);
    try {
      // 1. Index the page on demand (no-op if already indexed for this URL)
      const ensured = (window as unknown as { ragEnsureIndexed?: () => Promise<boolean> })
        .ragEnsureIndexed;
      if (!ensured) throw new Error('Indexing unavailable');
      const ok = await ensured();
      if (!ok) throw new Error('Could not analyze this page');

      const st = indexingState.getState();
      if (!st.sessionId) throw new Error('Page session missing');

      // 2. Create a workspace if none exists yet
      let targetId = activeId;
      if (!targetId) {
        const ws = await createWorkspace('My Knowledge Base');
        targetId = ws.workspace_id;
      }

      // 3. Register the page
      const ws = await addPageToWorkspace(targetId, {
        session_id: st.sessionId,
        url: window.location.href,
        title: st.pageTitle || document.title,
        chunks: 0, // backend reports real count; entry is informational
      });

      await workspaceState.refresh();
      await workspaceState.setActive(targetId);
      setAddedMsg(`Added to "${ws.name}" (${ws.pages.length} pages)`);
      setTimeout(() => setAddedMsg(null), 4000);
    } catch (err) {
      setAddedMsg(err instanceof Error ? err.message : 'Failed to add page');
      setTimeout(() => setAddedMsg(null), 4000);
    } finally {
      setAdding(false);
    }
  };

  /** Quick-create a new workspace inline. */
  const handleCreate = async () => {
    const name = window.prompt('Name your knowledge base:', 'My Knowledge Base');
    if (!name) return;
    try {
      const ws = await createWorkspace(name);
      await workspaceState.refresh();
      await workspaceState.setActive(ws.workspace_id);
    } catch {
      // silently ignore — refresh will reflect state
    }
  };

  const pageCount = active?.pages.length ?? 0;

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {/* Scope selector row */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <button
          className="rag-ws-trigger"
          onClick={() => setExpanded((e) => !e)}
          title="Choose what Changayi answers from"
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: theme.ctxBg,
            border: 'none',
            borderRadius: 8,
            padding: '5px 10px',
            cursor: 'pointer',
            color: theme.ctxText,
            fontSize: 12,
            fontWeight: 500,
            textAlign: 'left',
            fontFamily: 'inherit',
          }}
        >
          <span style={{ fontSize: 12 }}>{active ? '📚' : '📄'}</span>
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {active ? `${active.name} (${pageCount} page${pageCount === 1 ? '' : 's'})` : 'Current page only'}
          </span>
          <span style={{ fontSize: 9, opacity: 0.7 }}>{expanded ? '▲' : '▼'}</span>
        </button>

        {/* Add-to-KB button */}
        <button
          className="rag-ws-add"
          onClick={() => void handleAddToKb()}
          disabled={adding || isIndexing}
          title="Analyze this page (if needed) and add it to the knowledge base"
          style={{
            background: adding ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.25)',
            border: 'none',
            borderRadius: 8,
            padding: '5px 9px',
            cursor: adding ? 'wait' : 'pointer',
            color: '#fff',
            fontSize: 12,
            fontWeight: 600,
            fontFamily: 'inherit',
            whiteSpace: 'nowrap',
          }}
        >
          {adding ? '…' : '+ KB'}
        </button>
      </div>

      {/* Status feedback */}
      {addedMsg && (
        <p style={{
          margin: '4px 2px 0',
          fontSize: 11,
          color: theme.ctxText,
          fontWeight: 500,
        }}>
          {addedMsg}
        </p>
      )}

      {/* Dropdown */}
      {expanded && (
        <div
          className="rag-ws-menu"
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            background: theme.msgBg,
            border: `1px solid ${theme.msgBorder}`,
            borderRadius: 12,
            boxShadow: '0 12px 32px rgba(0,0,0,0.25)',
            zIndex: 10,
            overflow: 'hidden',
          }}
        >
          {/* Option: current page only */}
          <button
            onClick={() => {
              void workspaceState.setActive(null);
              setExpanded(false);
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
              padding: '10px 12px',
              background: activeId === null ? theme.inlineCodeBg : 'transparent',
              border: 'none',
              cursor: 'pointer',
              textAlign: 'left',
              fontSize: 13,
              color: theme.msgText,
              fontFamily: 'inherit',
            }}
          >
            📄 Current page only
            {activeId === null && <span style={{ marginLeft: 'auto' }}>✓</span>}
          </button>

          {/* Existing workspaces */}
          {workspaces.map((ws) => (
            <button
              key={ws.workspace_id}
              onClick={() => {
                void workspaceState.setActive(ws.workspace_id);
                setExpanded(false);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: '10px 12px',
                background: activeId === ws.workspace_id ? theme.inlineCodeBg : 'transparent',
                border: 'none',
                borderTop: `1px solid ${theme.msgBorder}`,
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: 13,
                color: theme.msgText,
                fontFamily: 'inherit',
              }}
            >
              📚 {ws.name}
              <span style={{ marginLeft: 'auto', fontSize: 11, opacity: 0.6 }}>
                {ws.pages.length} page{ws.pages.length === 1 ? '' : 's'}
              </span>
              {activeId === ws.workspace_id && <span>✓</span>}
            </button>
          ))}

          {/* Create new */}
          <button
            onClick={() => {
              setExpanded(false);
              void handleCreate();
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
              padding: '10px 12px',
              background: 'transparent',
              border: 'none',
              borderTop: `1px solid ${theme.msgBorder}`,
              cursor: 'pointer',
              textAlign: 'left',
              fontSize: 13,
              fontWeight: 600,
              color: '#6366f1',
              fontFamily: 'inherit',
            }}
          >
            ＋ New knowledge base
          </button>
        </div>
      )}
    </div>
  );
};

export default WorkspacePicker;
