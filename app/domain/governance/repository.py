from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.enums import GovernanceEntityType
from app.domain.governance.change_log import ConfigChangeLog


class IConfigChangeLogRepository(ABC):
    """Port — append-only governance change journal."""

    @abstractmethod
    def append(self, log: ConfigChangeLog) -> ConfigChangeLog: ...

    @abstractmethod
    def find_all(
        self,
        entity_type: Optional[GovernanceEntityType] = None,
        entity_key: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConfigChangeLog]: ...

    @abstractmethod
    def count(
        self,
        entity_type: Optional[GovernanceEntityType] = None,
        entity_key: Optional[str] = None,
    ) -> int: ...
