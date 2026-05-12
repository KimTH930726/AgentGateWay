from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Agent:
    agent_id: str
    name: str
    allowed_domains: List[str]
    enabled: bool

    def can_access_domain(self, domain: str) -> bool:
        return domain in self.allowed_domains
