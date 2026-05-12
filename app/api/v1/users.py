from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_user_repo
from app.api.schemas import UserCreate, UserResponse
from app.domain.user.user import User
from app.infrastructure.persistence.repositories.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(body: UserCreate, repo: UserRepository = Depends(get_user_repo)):
    if repo.find_by_user_id(body.user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    return repo.save(User(user_id=body.user_id, roles=body.roles, enabled=True))


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, repo: UserRepository = Depends(get_user_repo)):
    user = repo.find_by_user_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
