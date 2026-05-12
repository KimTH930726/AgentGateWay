from typing import Optional

from sqlalchemy.orm import Session

from app.domain.user.repository import IUserRepository
from app.domain.user.user import User
from app.infrastructure.persistence.orm_models import UserORM


class UserRepository(IUserRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def _to_domain(self, row: UserORM) -> User:
        return User(user_id=row.user_id, roles=row.roles or [], enabled=row.enabled)

    def find_by_user_id(self, user_id: str) -> Optional[User]:
        row = self._db.query(UserORM).filter(UserORM.user_id == user_id).first()
        return self._to_domain(row) if row else None

    def save(self, user: User) -> User:
        row = UserORM(user_id=user.user_id, roles=user.roles, enabled=user.enabled)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._to_domain(row)
