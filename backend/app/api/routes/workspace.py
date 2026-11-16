"""
workspace.py — API routes for multi-tab knowledge bases ("workspaces").

Endpoints:
  POST /api/workspace/create         — create an empty workspace
  GET  /api/workspace/list           — list all workspaces
  GET  /api/workspace/{id}           — get one workspace with its pages
  POST /api/workspace/{id}/add_page  — register an indexed page into the workspace
  POST /api/workspace/{id}/remove_page — remove a page entry
  DELETE /api/workspace/{id}         — delete the workspace

Flow: the extension indexes each tab through the normal /api/page/index
endpoint, then registers it here. Questions with a workspace_id are
answered across ALL pages in the workspace (see chat_service).
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    WorkspaceResponse,
    WorkspacePage,
    CreateWorkspaceRequest,
    AddPageRequest,
)
from app.services import workspace_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspace")


def _to_response(ws: dict) -> WorkspaceResponse:
    return WorkspaceResponse(
        workspace_id=ws["workspace_id"],
        name=ws["name"],
        pages=[WorkspacePage(**p) for p in ws["pages"]],
        created_at=ws["created_at"],
    )


@router.post("/create", response_model=WorkspaceResponse)
async def create_workspace(request: CreateWorkspaceRequest) -> WorkspaceResponse:
    """Creates a new, empty workspace."""
    ws = workspace_service.create_workspace(request.name)
    return _to_response(ws)


@router.get("/list", response_model=list[WorkspaceResponse])
async def list_workspaces() -> list[WorkspaceResponse]:
    """Lists every workspace, newest first."""
    return [_to_response(ws) for ws in workspace_service.list_workspaces()]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str) -> WorkspaceResponse:
    ws = workspace_service.get_workspace(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    return _to_response(ws)


@router.post("/{workspace_id}/add_page", response_model=WorkspaceResponse)
async def add_page(workspace_id: str, request: AddPageRequest) -> WorkspaceResponse:
    """
    Registers an already-indexed page into the workspace.
    The page must exist in ChromaDB (indexed via /api/page/index).
    Re-adding the same URL replaces the previous entry (re-index case).
    """
    try:
        ws = workspace_service.add_page(
            workspace_id=workspace_id,
            session_id=request.session_id,
            url=request.url,
            title=request.title,
            chunks=request.chunks,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_response(ws)


@router.post("/{workspace_id}/remove_page", response_model=WorkspaceResponse)
async def remove_page(workspace_id: str, url: str) -> WorkspaceResponse:
    """Removes a page entry from the workspace. The page's Chroma collection is kept."""
    try:
        ws = workspace_service.remove_page(workspace_id, url)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_response(ws)


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str) -> dict:
    deleted = workspace_service.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    return {"success": True, "message": f"Workspace '{workspace_id}' deleted"}
