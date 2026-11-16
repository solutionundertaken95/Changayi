/**
 * workspaceState.ts — Shared workspace (Multi-Tab KB) selection state.
 *
 * Minimal pub/sub singleton (same pattern as indexingState):
 *   - ChatPanel reads `activeWorkspaceId` to decide the retrieval scope
 *     (null = current page only, set = search across all KB pages)
 *   - The WorkspacePicker component updates it
 *
 * The selected workspace is remembered per browser via chrome.storage.local
 * so it survives panel close/open and page navigation.
 */

import type { Workspace } from "../types";
import { listWorkspaces } from "../services/api";

// Declare the chrome API globally so TypeScript resolves it even when
// @types/chrome isn't in every consumer's compilation path.
declare const chrome: {
  storage: {
    local: {
      get: (keys: string[]) => Promise<Record<string, unknown>>;
      set: (items: Record<string, unknown>) => Promise<void>;
      remove: (keys: string | string[]) => Promise<void>;
    };
  };
};

type Listener = (workspaceId: string | null, workspaces: Workspace[]) => void;

class WorkspaceStateManager {
  private activeWorkspaceId: string | null = null;
  private workspaces: Workspace[] = [];
  private listeners: Listener[] = [];
  private loaded = false;

  async load(): Promise<void> {
    if (this.loaded) return;
    this.loaded = true;

    // Restore last active workspace selection
    try {
      const stored = await chrome.storage.local.get(["activeWorkspaceId"]);
      if (stored.activeWorkspaceId) {
        this.activeWorkspaceId = stored.activeWorkspaceId as string;
      }
    } catch {
      // chrome.storage unavailable (e.g. dev outside extension) — ignore
    }

    // Fetch workspace list from backend
    try {
      this.workspaces = await listWorkspaces();

      // Drop the stored selection if that workspace no longer exists
      if (
        this.activeWorkspaceId &&
        !this.workspaces.some((w) => w.workspace_id === this.activeWorkspaceId)
      ) {
        this.activeWorkspaceId = null;
        await chrome.storage.local.remove("activeWorkspaceId");
      }
    } catch {
      // Backend offline — keep whatever we have; retry on next refresh()
    }

    this.notify();
  }

  async refresh(): Promise<void> {
    this.loaded = false;
    await this.load();
  }

  getActiveWorkspaceId(): string | null {
    return this.activeWorkspaceId;
  }

  getWorkspaces(): Workspace[] {
    return this.workspaces;
  }

  getActiveWorkspace(): Workspace | null {
    return (
      this.workspaces.find((w) => w.workspace_id === this.activeWorkspaceId) ??
      null
    );
  }

  /** Select a workspace (or null to scope back to the current page). */
  async setActive(workspaceId: string | null): Promise<void> {
    this.activeWorkspaceId = workspaceId;
    try {
      if (workspaceId) {
        await chrome.storage.local.set({ activeWorkspaceId: workspaceId });
      } else {
        await chrome.storage.local.remove("activeWorkspaceId");
      }
    } catch {
      // Non-fatal — in-memory selection still works for this session
    }
    this.notify();
  }

  subscribe(listener: Listener): () => void {
    this.listeners.push(listener);
    listener(this.activeWorkspaceId, this.workspaces);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private notify(): void {
    this.listeners.forEach((l) => l(this.activeWorkspaceId, this.workspaces));
  }
}

export const workspaceState = new WorkspaceStateManager();
