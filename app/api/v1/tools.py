from typing import List, Optional

from fastapi import APIRouter, Depends, Header, status

from app.api.deps import (
    get_delete_tool, get_get_tool, get_list_tools,
    get_register_tool, get_update_tool,
)
from app.api.schemas import ToolCreate, ToolResponse, ToolUpdate
from app.application.tool.use_cases import (
    DeleteToolCommand, DeleteToolUseCase, GetToolUseCase, ListToolsUseCase,
    RegisterToolCommand, RegisterToolUseCase, UpdateToolCommand, UpdateToolUseCase,
)

router = APIRouter(prefix="/tools", tags=["Tool Registry"])

_ACTOR_HEADER = "X-Acting-User"
_REASON_HEADER = "X-Change-Reason"


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
def register_tool(
    body: ToolCreate,
    uc: RegisterToolUseCase = Depends(get_register_tool),
    x_acting_user: Optional[str] = Header(default=None, alias=_ACTOR_HEADER),
    x_change_reason: Optional[str] = Header(default=None, alias=_REASON_HEADER),
):
    return uc.execute(RegisterToolCommand(
        **body.model_dump(),
        changed_by=x_acting_user or "",
        change_reason=x_change_reason or "",
    ))


@router.get("", response_model=List[ToolResponse])
def list_tools(uc: ListToolsUseCase = Depends(get_list_tools)):
    return uc.execute()


@router.get("/{tool_id}", response_model=ToolResponse)
def get_tool(tool_id: str, uc: GetToolUseCase = Depends(get_get_tool)):
    return uc.execute(tool_id)


@router.patch("/{tool_id}", response_model=ToolResponse)
def update_tool(
    tool_id: str,
    body: ToolUpdate,
    uc: UpdateToolUseCase = Depends(get_update_tool),
    x_acting_user: Optional[str] = Header(default=None, alias=_ACTOR_HEADER),
    x_change_reason: Optional[str] = Header(default=None, alias=_REASON_HEADER),
):
    return uc.execute(UpdateToolCommand(
        tool_id=tool_id,
        updates=body.model_dump(exclude_none=True),
        changed_by=x_acting_user or "",
        change_reason=x_change_reason or "",
    ))


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(
    tool_id: str,
    uc: DeleteToolUseCase = Depends(get_delete_tool),
    x_acting_user: Optional[str] = Header(default=None, alias=_ACTOR_HEADER),
    x_change_reason: Optional[str] = Header(default=None, alias=_REASON_HEADER),
):
    uc.execute(DeleteToolCommand(
        tool_id=tool_id,
        changed_by=x_acting_user or "",
        change_reason=x_change_reason or "",
    ))
