from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_agent_repo, get_tool_call_repo
from app.api.schemas import AgentCreate, AgentResponse, AgentUpdate, AgentUsageResponse
from app.domain.agent.agent import Agent
from app.infrastructure.persistence.repositories.agent_repository import AgentRepository
from app.infrastructure.persistence.repositories.tool_call_repository import ToolCallRepository

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def register_agent(body: AgentCreate, repo: AgentRepository = Depends(get_agent_repo)):
    if repo.find_by_agent_id(body.agent_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent already exists")
    agent = repo.save(Agent(
        agent_id=body.agent_id,
        name=body.name,
        allowed_domains=body.allowed_domains,
        enabled=True,
        daily_cost_limit=body.daily_cost_limit,
        monthly_cost_limit=body.monthly_cost_limit,
        daily_token_limit=body.daily_token_limit,
        daily_cost_warn_threshold=body.daily_cost_warn_threshold,
    ))
    return agent


@router.get("", response_model=List[AgentResponse])
def list_agents(repo: AgentRepository = Depends(get_agent_repo)):
    return repo.find_all()


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, repo: AgentRepository = Depends(get_agent_repo)):
    agent = repo.find_by_agent_id(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    body: AgentUpdate,
    repo: AgentRepository = Depends(get_agent_repo),
):
    """Patch agent fields including governance budgets.

    Returns the updated agent. Change-log emission for agent edits is
    intentionally not wired in this MVP — agent ownership semantics belong
    to a future identity bounded context.
    """
    updates = body.model_dump(exclude_none=True)
    if not updates:
        agent = repo.find_by_agent_id(agent_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return agent
    agent = repo.update(agent_id, updates)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.get("/{agent_id}/usage", response_model=AgentUsageResponse)
def get_agent_usage(
    agent_id: str,
    agent_repo: AgentRepository = Depends(get_agent_repo),
    tool_call_repo: ToolCallRepository = Depends(get_tool_call_repo),
):
    agent = agent_repo.find_by_agent_id(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return AgentUsageResponse(
        agent_id=agent.agent_id,
        daily_cost=tool_call_repo.get_agent_daily_cost(agent_id),
        monthly_cost=tool_call_repo.get_agent_monthly_cost(agent_id),
        daily_tokens=tool_call_repo.get_agent_daily_tokens(agent_id),
        daily_cost_limit=agent.daily_cost_limit,
        daily_cost_warn_threshold=agent.daily_cost_warn_threshold,
        daily_token_limit=agent.daily_token_limit,
    )
