from pydantic import BaseModel

from app.models import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthUser(BaseModel):
    id: int
    username: str
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: AuthUser
