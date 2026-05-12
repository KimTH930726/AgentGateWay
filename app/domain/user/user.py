from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class User:
    user_id: str
    roles: List[str]
    enabled: bool

    def has_role(self, role: str) -> bool:
        return role in self.roles
