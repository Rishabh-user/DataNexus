from datetime import datetime, timedelta, timezone
from typing import Callable

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

security_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    from app.models.user import User

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_roles(*roles: str) -> Callable:
    """
    Dependency factory — returns a FastAPI dependency that enforces role access.

    Usage:
        @router.post("/upload")
        async def upload(current_user = Depends(require_roles("analyst", "admin", "superadmin"))):
            ...

    The legacy role value "user" is treated as "analyst".
    """
    allowed = set(roles)

    async def _checker(
        credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
        db: AsyncSession = Depends(get_db),
    ):
        user = await get_current_user(credentials, db)
        # Map legacy "user" → "analyst" for backwards compatibility
        effective_role = "analyst" if user.role == "user" else user.role
        if effective_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {' or '.join(sorted(allowed))}",
            )
        return user

    return _checker


# Convenience pre-built dependencies
def require_admin():
    """Allows admin and superadmin."""
    return require_roles("admin", "superadmin")


def require_superadmin():
    """Allows superadmin only."""
    return require_roles("superadmin")


def require_analyst_or_above():
    """Allows analyst, admin, and superadmin (not viewer)."""
    return require_roles("analyst", "admin", "superadmin")
