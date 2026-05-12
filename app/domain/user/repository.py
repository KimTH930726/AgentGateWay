from abc import ABC, abstractmethod
from typing import Optional

from app.domain.user.user import User


class IUserRepository(ABC):

    @abstractmethod
    def find_by_user_id(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    def save(self, user: User) -> User: ...
