"""
Authentication Schemas
Pydantic models for auth requests and responses.
"""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login form data."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """User data for API responses."""
    id: str
    username: str
    full_name: str | None
    is_admin: bool

    class Config:
        from_attributes = True


class TokenData(BaseModel):
    """Data stored in JWT token."""
    user_id: str
    username: str
