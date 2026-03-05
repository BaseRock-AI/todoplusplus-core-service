from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db import get_db
from app.models import User
from app.repositories import get_user_by_username
from app.schemas_auth import AuthUser, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = get_user_by_username(db, payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    token = create_access_token(subject=str(user.id), role=user.role, expires_delta=expires_delta)

    return TokenResponse(
        access_token=token,
        expires_in_seconds=settings.jwt_access_token_expire_minutes * 60,
        user=AuthUser(id=user.id, username=user.username, role=user.role),
    )


@router.get("/me", response_model=AuthUser)
def get_me(current_user: User = Depends(get_current_user)) -> AuthUser:
    return AuthUser(id=current_user.id, username=current_user.username, role=current_user.role)
