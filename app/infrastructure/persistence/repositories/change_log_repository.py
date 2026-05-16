import uuid
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.enums import ChangeType, GovernanceEntityType
from app.domain.governance.change_log import ConfigChangeLog
from app.domain.governance.repository import IConfigChangeLogRepository
from app.infrastructure.persistence.orm_models import ConfigChangeLogORM


class ConfigChangeLogRepository(IConfigChangeLogRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def _to_domain(self, row: ConfigChangeLogORM) -> ConfigChangeLog:
        return ConfigChangeLog(
            log_id=str(row.id),
            entity_type=GovernanceEntityType(row.entity_type),
            entity_key=row.entity_key,
            change_type=ChangeType(row.change_type),
            before=row.before,
            after=row.after,
            reason=row.reason or "",
            changed_by=row.changed_by or "",
            changed_at=row.changed_at,
        )

    def append(self, log: ConfigChangeLog) -> ConfigChangeLog:
        row = ConfigChangeLogORM(
            id=uuid.UUID(log.log_id),
            entity_type=log.entity_type,
            entity_key=log.entity_key,
            change_type=log.change_type,
            before=log.before,
            after=log.after,
            reason=log.reason,
            changed_by=log.changed_by,
            changed_at=log.changed_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._to_domain(row)

    def find_all(
        self,
        entity_type: Optional[GovernanceEntityType] = None,
        entity_key: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConfigChangeLog]:
        q = self._db.query(ConfigChangeLogORM)
        if entity_type is not None:
            q = q.filter(ConfigChangeLogORM.entity_type == entity_type)
        if entity_key is not None:
            q = q.filter(ConfigChangeLogORM.entity_key == entity_key)
        rows = (
            q.order_by(ConfigChangeLogORM.changed_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(r) for r in rows]

    def count(
        self,
        entity_type: Optional[GovernanceEntityType] = None,
        entity_key: Optional[str] = None,
    ) -> int:
        q = self._db.query(func.count(ConfigChangeLogORM.id))
        if entity_type is not None:
            q = q.filter(ConfigChangeLogORM.entity_type == entity_type)
        if entity_key is not None:
            q = q.filter(ConfigChangeLogORM.entity_key == entity_key)
        return int(q.scalar() or 0)
