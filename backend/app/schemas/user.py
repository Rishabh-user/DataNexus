from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.models.user import UserRole


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """User updating their own profile."""
    full_name: str | None = None
    email: EmailStr | None = None


# ─── Admin schemas ─────────────────────────────────────────────────────────────

class AdminUserCreate(BaseModel):
    """Admin creating a new user — includes role assignment."""
    email: EmailStr
    password: str
    full_name: str
    role: str = UserRole.ANALYST

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in UserRole.ALL:
            raise ValueError(f"Invalid role '{v}'. Must be one of: {', '.join(sorted(UserRole.ALL))}")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class AdminUserUpdate(BaseModel):
    """Admin updating another user — can change role and active status."""
    full_name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in UserRole.ALL:
            raise ValueError(f"Invalid role '{v}'. Must be one of: {', '.join(sorted(UserRole.ALL))}")
        return v


class UserListItem(BaseModel):
    """Compact user representation for list views."""
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated list of users for admin panel."""
    items: list[UserListItem]
    total: int
    skip: int
    limit: int
    has_more: bool


class SystemStats(BaseModel):
    """System-wide statistics for the admin dashboard."""
    total_users: int
    active_users: int
    inactive_users: int
    roles_breakdown: dict[str, int]
    total_files: int
    total_reports: int
    total_chat_sessions: int


class UserActivitySummary(BaseModel):
    """Activity summary for a specific user (admin view)."""
    user: UserResponse
    file_count: int
    report_count: int
    chat_session_count: int
    last_active: datetime | None
