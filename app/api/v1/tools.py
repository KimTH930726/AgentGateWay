from typing import List

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    get_delete_tool, get_get_tool, get_list_tools,
    get_register_tool, get_update_tool,
)
from app.api.schemas import ToolCreate, ToolResponse, ToolUpdate
from app.application.tool.use_cases import (
    DeleteToolUseCase, GetToolUseCase, ListToolsUseCase,
    RegisterToolCommand, RegisterToolUseCase, UpdateToolCommand, UpdateToolUseCase,
)

router = APIRouter(prefix="/tools", tags=["Tool Registry"])


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
def register_tool(body: ToolCreate, uc: RegisterToolUseCase = Depends(get_register_tool)):
    return uc.execute(RegisterToolCommand(**body.model_dump()))


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
):
    return uc.execute(UpdateToolCommand(tool_id=tool_id, updates=body.model_dump(exclude_none=True)))


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(tool_id: str, uc: DeleteToolUseCase = Depends(get_delete_tool)):
    uc.execute(tool_id)
