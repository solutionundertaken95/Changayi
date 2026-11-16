"""
workspace_service.py — Multi-tab knowledge bases ("workspaces").

A workspace groups several indexed pages into ONE searchable corpus.
Each page keeps its own Chroma collection (so single-page sessions
keep working unchanged); a workspace is just a registry of the
session_ids belonging to it, persisted as JSON on disk.

--- WHY THIS IS WHERE HYBRID + RERANK SHINE ---

With one page indexed (~12 chunks), dense-only retrieval is nearly
solved. With 5 tabs (~50–100+ chunks) from DIFFERENT documents:

  - Dense vectors from different docs aren't directly comparable
    (each doc's chunk vectors cluster around their own topic center).
  - BM25 catches exact tokens (model numbers, names) that appear on
    only one tab.
  - Candidates from different tabs compete, and only the cross-encoder
    reranker — which sees (query, chunk) jointly — can arbitrate fairly.

--- STORAGE ---

  data/workspaces/
      {workspace_id}.json   →  { workspace_id, name, pages: [...] }

  Each page entry: { session_id, url, title, chunks, indexed_at }
"""

import json
import logging
import threading
import time
import uuid
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_WORKSPACES_DIR = Path(settings.workspace_store_dir)
_LOCK = threading.Lock()


# ------------------------------------------------------------------
# Persistence helpers
# ------------------------------------------------------------------


def _ws_path(workspace_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in workspace_id)
    return _WORKSPACES_DIR / f"{safe}.json"


def _load(workspace_id: str) -> dict | None:
    path = _ws_path(workspace_id)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(workspace: dict) -> None:
    _WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    with open(_ws_path(workspace["workspace_id"]), "w", encoding="utf-8") as f:
        json.dump(workspace, f, indent=2)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def create_workspace(name: str) -> dict:
    """Creates an empty workspace and returns it."""
    workspace = {
        "workspace_id": f"ws-{uuid.uuid4().hex[:12]}",
        "name": name.strip() or "Untitled workspace",
        "pages": [],
        "created_at": time.time(),
    }
    with _LOCK:
        _save(workspace)
    logger.info(f"Created workspace '{workspace['name']}' [{workspace['workspace_id']}]")
    return workspace


def get_workspace(workspace_id: str) -> dict | None:
    """Returns the workspace dict, or None if it doesn't exist."""
    with _LOCK:
        return _load(workspace_id)


def list_workspaces() -> list[dict]:
    """Returns all workspaces, newest first."""
    if not _WORKSPACES_DIR.exists():
        return []
    out = []
    for path in _WORKSPACES_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            continue
    return sorted(out, key=lambda w: w.get("created_at", 0), reverse=True)


def add_page(
    workspace_id: str,
    session_id: str,
    url: str,
    title: str,
    chunks: int,
) -> dict:
    """
    Registers an already-indexed page into a workspace.
    Idempotent per (workspace, url): re-adding updates the entry.
    """
    with _LOCK:
        workspace = _load(workspace_id)
        if workspace is None:
            raise ValueError(f"Workspace '{workspace_id}' does not exist")

        entry = {
            "session_id": session_id,
            "url": url,
            "title": title,
            "chunks": chunks,
            "indexed_at": time.time(),
        }

        # Replace an existing entry for the same URL (page was re-indexed)
        workspace["pages"] = [p for p in workspace["pages"] if p["url"] != url]
        workspace["pages"].append(entry)

        _save(workspace)

    logger.info(
        f"Added page '{title}' ({chunks} chunks) to workspace "
        f"'{workspace['name']}' — now {len(workspace['pages'])} pages"
    )
    return workspace


def remove_page(workspace_id: str, url: str) -> dict:
    """Removes a page entry from the workspace (does not delete its collection)."""
    with _LOCK:
        workspace = _load(workspace_id)
        if workspace is None:
            raise ValueError(f"Workspace '{workspace_id}' does not exist")
        before = len(workspace["pages"])
        workspace["pages"] = [p for p in workspace["pages"] if p["url"] != url]
        _save(workspace)
    logger.info(f"Removed {before - len(workspace['pages'])} page(s) from workspace '{workspace_id}'")
    return workspace


def delete_workspace(workspace_id: str) -> bool:
    with _LOCK:
        path = _ws_path(workspace_id)
        if not path.exists():
            return False
        path.unlink()
    logger.info(f"Deleted workspace '{workspace_id}'")
    return True


def workspace_session_ids(workspace_id: str) -> list[str]:
    """The session_ids of every page in the workspace — the fan-out targets."""
    workspace = get_workspace(workspace_id)
    if workspace is None:
        return []
    return [p["session_id"] for p in workspace["pages"]]
