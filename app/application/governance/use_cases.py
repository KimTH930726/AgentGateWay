from dataclasses import dataclass
from typing import List, Optional

from app.domain.enums import GovernanceEntityType
from app.domain.governance.change_log import ConfigChangeLog
from app.domain.governance.repository import IConfigChangeLogRepository


@dataclass(frozen=True)
class ChangeLogPage:
    items: List[ConfigChangeLog]
    total: int
    limit: int
    offset: int

    @property
    def has_next(self) -> bool:
        return (self.offset + self.limit) < self.total


class ListChangeLogsUseCase:
    def __init__(self, repo: IConfigChangeLogRepository) -> None:
        self._repo = repo

    def execute(
        self,
        entity_type: Optional[GovernanceEntityType] = None,
        entity_key: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ChangeLogPage:
        items = self._repo.find_all(
            entity_type=entity_type,
            entity_key=entity_key,
            limit=limit,
            offset=offset,
        )
        total = self._repo.count(entity_type=entity_type, entity_key=entity_key)
        return ChangeLogPage(items=items, total=total, limit=limit, offset=offset)
