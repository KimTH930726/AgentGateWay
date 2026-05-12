from typing import List, Optional

from sqlalchemy.orm import Session

from app.domain.enums import RiskLevel
from app.domain.tool.repository import IToolRepository
from app.domain.tool.tool import Tool
from app.infrastructure.persistence.orm_models import ToolORM


class ToolRepository(IToolRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def _to_domain(self, row: ToolORM) -> Tool:
        return Tool(
            tool_id=row.tool_id,
            name=row.name,
            description=row.description,
            domain=row.domain,
            risk_level=RiskLevel(row.risk_level),
            required_role=row.required_role,
            approval_required=row.approval_required,
            sandbox_supported=row.sandbox_supported,
            daily_cost_limit=row.daily_cost_limit,
            enabled=row.enabled,
        )

    def find_by_tool_id(self, tool_id: str) -> Optional[Tool]:
        row = self._db.query(ToolORM).filter(ToolORM.tool_id == tool_id).first()
        return self._to_domain(row) if row else None

    def find_by_name(self, name: str) -> Optional[Tool]:
        row = self._db.query(ToolORM).filter(ToolORM.name == name).first()
        return self._to_domain(row) if row else None

    def find_all(self) -> List[Tool]:
        return [self._to_domain(r) for r in self._db.query(ToolORM).all()]

    def save(self, tool: Tool) -> Tool:
        row = ToolORM(
            tool_id=tool.tool_id,
            name=tool.name,
            description=tool.description,
            domain=tool.domain,
            risk_level=tool.risk_level,
            required_role=tool.required_role,
            approval_required=tool.approval_required,
            sandbox_supported=tool.sandbox_supported,
            daily_cost_limit=tool.daily_cost_limit,
            enabled=tool.enabled,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._to_domain(row)

    def update(self, tool_id: str, updates: dict) -> Optional[Tool]:
        row = self._db.query(ToolORM).filter(ToolORM.tool_id == tool_id).first()
        if not row:
            return None
        for key, value in updates.items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._to_domain(row)

    def delete(self, tool_id: str) -> bool:
        row = self._db.query(ToolORM).filter(ToolORM.tool_id == tool_id).first()
        if not row:
            return False
        self._db.delete(row)
        self._db.commit()
        return True
