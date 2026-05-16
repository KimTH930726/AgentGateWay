import uuid
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.agent_tool_policy.agent_tool_policy import AgentToolPolicy
from app.domain.agent_tool_policy.repository import IAgentToolPolicyRepository
from app.domain.enums import AgentToolPolicyType
from app.domain.shared.exceptions import ConflictError
from app.infrastructure.persistence.orm_models import AgentToolPolicyORM


class AgentToolPolicyRepository(IAgentToolPolicyRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def _to_domain(self, row: AgentToolPolicyORM) -> AgentToolPolicy:
        return AgentToolPolicy(
            policy_id=str(row.id),
            agent_id=row.agent_id,
            tool_name=row.tool_name,
            policy_type=AgentToolPolicyType(row.policy_type),
            enabled=row.enabled,
            reason=row.reason or "",
            created_by=row.created_by or "",
            created_at=row.created_at,
        )

    def save(self, policy: AgentToolPolicy) -> AgentToolPolicy:
        row = AgentToolPolicyORM(
            id=uuid.UUID(policy.policy_id),
            agent_id=policy.agent_id,
            tool_name=policy.tool_name,
            policy_type=policy.policy_type,
            enabled=policy.enabled,
            reason=policy.reason,
            created_by=policy.created_by,
            created_at=policy.created_at,
            updated_at=policy.created_at,
        )
        self._db.add(row)
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ConflictError(
                f"AgentToolPolicy already exists for agent={policy.agent_id}, "
                f"tool={policy.tool_name}, type={policy.policy_type.value}"
            ) from exc
        self._db.refresh(row)
        return self._to_domain(row)

    def find_by_id(self, policy_id: str) -> Optional[AgentToolPolicy]:
        try:
            pid = uuid.UUID(policy_id)
        except (ValueError, AttributeError):
            return None
        row = self._db.query(AgentToolPolicyORM).filter(AgentToolPolicyORM.id == pid).first()
        return self._to_domain(row) if row else None

    def find_by_agent(self, agent_id: str) -> List[AgentToolPolicy]:
        rows = (
            self._db.query(AgentToolPolicyORM)
            .filter(AgentToolPolicyORM.agent_id == agent_id)
            .order_by(AgentToolPolicyORM.created_at.desc())
            .all()
        )
        return [self._to_domain(r) for r in rows]

    def find_all(self) -> List[AgentToolPolicy]:
        rows = (
            self._db.query(AgentToolPolicyORM)
            .order_by(AgentToolPolicyORM.created_at.desc())
            .all()
        )
        return [self._to_domain(r) for r in rows]

    def update(self, policy_id: str, updates: dict) -> Optional[AgentToolPolicy]:
        try:
            pid = uuid.UUID(policy_id)
        except (ValueError, AttributeError):
            return None
        row = self._db.query(AgentToolPolicyORM).filter(AgentToolPolicyORM.id == pid).first()
        if not row:
            return None
        for key, value in updates.items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._to_domain(row)

    def delete(self, policy_id: str) -> bool:
        try:
            pid = uuid.UUID(policy_id)
        except (ValueError, AttributeError):
            return False
        row = self._db.query(AgentToolPolicyORM).filter(AgentToolPolicyORM.id == pid).first()
        if not row:
            return False
        self._db.delete(row)
        self._db.commit()
        return True
