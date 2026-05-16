from typing import List, Optional

from sqlalchemy.orm import Session

from app.domain.agent.agent import Agent
from app.domain.agent.repository import IAgentRepository
from app.infrastructure.persistence.orm_models import AgentORM


class AgentRepository(IAgentRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def _to_domain(self, row: AgentORM) -> Agent:
        return Agent(
            agent_id=row.agent_id,
            name=row.name,
            allowed_domains=row.allowed_domains or [],
            enabled=row.enabled,
            daily_cost_limit=row.daily_cost_limit,
            monthly_cost_limit=row.monthly_cost_limit,
            daily_token_limit=row.daily_token_limit,
            daily_cost_warn_threshold=row.daily_cost_warn_threshold,
        )

    def find_by_agent_id(self, agent_id: str) -> Optional[Agent]:
        row = self._db.query(AgentORM).filter(AgentORM.agent_id == agent_id).first()
        return self._to_domain(row) if row else None

    def find_all(self) -> List[Agent]:
        return [self._to_domain(r) for r in self._db.query(AgentORM).all()]

    def save(self, agent: Agent) -> Agent:
        row = AgentORM(
            agent_id=agent.agent_id,
            name=agent.name,
            allowed_domains=agent.allowed_domains,
            enabled=agent.enabled,
            daily_cost_limit=agent.daily_cost_limit,
            monthly_cost_limit=agent.monthly_cost_limit,
            daily_token_limit=agent.daily_token_limit,
            daily_cost_warn_threshold=agent.daily_cost_warn_threshold,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._to_domain(row)

    def update(self, agent_id: str, updates: dict) -> Optional[Agent]:
        row = self._db.query(AgentORM).filter(AgentORM.agent_id == agent_id).first()
        if not row:
            return None
        for key, value in updates.items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._to_domain(row)
