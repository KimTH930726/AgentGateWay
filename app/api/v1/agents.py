from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_agent_repo
from app.api.schemas import AgentCreate, AgentResponse
from app.domain.agent.agent import Agent
from app.infrastructure.persistence.repositories.agent_repository import AgentRepository

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
