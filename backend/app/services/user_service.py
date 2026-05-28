"""User management service — admin operations."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.chat import ChatSession
from app.models.file import File
from app.models.report import Report
from app.models.user import User, UserRole
from app.schemas.user import AdminUserCreate, AdminUserUpdate, SystemStats, UserActivitySummary


async def list_all_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    search: str | None = None,
    role_filter: str | None = None,
    active_filter: bool | None = None,
) -> tuple[list[User], int]:
    """List all users with optional filters (admin only)."""
    q = select(User)
    count_q = select(func.count()).select_from(User)

    if search:
        pattern = f"%{search}%"
        from sqlalchemy import or_
        q = q.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
        count_q = count_q.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))

    if role_filter:
        q = q.where(User.role == role_filter)
        count_q = count_q.where(User.role == role_filter)

    if active_filter is not None:
        q = q.where(User.is_active == active_filter)
        count_q = count_q.where(User.is_active == active_filter)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = q.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    users = list(result.scalars().all())

    return users, total


async def get_user_by_id_admin(db: AsyncSession, user_id: int) -> User:
    """Fetch any user by ID (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def create_user_by_admin(
    db: AsyncSession,
    data: AdminUserCreate,
    created_by: User,
) -> User:
    """Create a new user — admin or superadmin only."""
    # Role assignment permission check
    if not UserRole.can_assign(created_by.role, data.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot assign the '{data.role}' role. "
                   f"Admins can only create users with analyst or viewer roles.",
        )

    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def update_user_by_admin(
    db: AsyncSession,
    user_id: int,
    data: AdminUserUpdate,
    acting_user: User,
) -> User:
    """Update any user's profile/role (admin only)."""
    user = await get_user_by_id_admin(db, user_id)

    # Prevent self-demotion of the only superadmin
    if user.id == acting_user.id and data.role and data.role != acting_user.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )

    # Role assignment permission check
    if data.role and data.role != user.role:
        if not UserRole.can_assign(acting_user.role, data.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You cannot assign the '{data.role}' role.",
            )

    if data.full_name is not None:
        user.full_name = data.full_name

    if data.email is not None and data.email != user.email:
        # Check uniqueness
        result = await db.execute(select(User).where(User.email == data.email, User.id != user_id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        user.email = data.email

    if data.role is not None:
        user.role = data.role

    if data.is_active is not None:
        # Prevent deactivating yourself
        if user.id == acting_user.id and not data.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account",
            )
        user.is_active = data.is_active

    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return user


async def toggle_user_active(
    db: AsyncSession,
    user_id: int,
    acting_user: User,
) -> User:
    """Toggle a user's is_active flag."""
    user = await get_user_by_id_admin(db, user_id)

    if user.id == acting_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    user.is_active = not user.is_active
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return user


async def delete_user_by_admin(
    db: AsyncSession,
    user_id: int,
    acting_user: User,
) -> None:
    """Permanently delete a user (superadmin only)."""
    user = await get_user_by_id_admin(db, user_id)

    if user.id == acting_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    await db.delete(user)
    await db.flush()


async def get_system_stats(db: AsyncSession) -> SystemStats:
    """Aggregate platform-wide statistics for admin dashboard."""
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    active_users = (await db.execute(select(func.count()).select_from(User).where(User.is_active == True))).scalar() or 0
    inactive_users = total_users - active_users

    # Roles breakdown
    roles_result = await db.execute(select(User.role, func.count(User.id)).group_by(User.role))
    roles_breakdown = {row[0]: row[1] for row in roles_result.all()}

    total_files = (await db.execute(select(func.count()).select_from(File))).scalar() or 0
    total_reports = (await db.execute(select(func.count()).select_from(Report))).scalar() or 0
    total_chats = (await db.execute(select(func.count()).select_from(ChatSession))).scalar() or 0

    return SystemStats(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        roles_breakdown=roles_breakdown,
        total_files=total_files,
        total_reports=total_reports,
        total_chat_sessions=total_chats,
    )


async def get_user_activity(db: AsyncSession, user_id: int) -> UserActivitySummary:
    """Get activity summary for a specific user."""
    user = await get_user_by_id_admin(db, user_id)

    file_count = (await db.execute(select(func.count()).select_from(File).where(File.user_id == user_id))).scalar() or 0
    report_count = (await db.execute(select(func.count()).select_from(Report).where(Report.user_id == user_id))).scalar() or 0
    chat_count = (await db.execute(select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id))).scalar() or 0

    # Last active = most recent chat session or file upload
    last_chat = await db.execute(
        select(ChatSession.updated_at).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc()).limit(1)
    )
    last_file = await db.execute(
        select(File.created_at).where(File.user_id == user_id).order_by(File.created_at.desc()).limit(1)
    )
    ts_chat = last_chat.scalar_one_or_none()
    ts_file = last_file.scalar_one_or_none()
    candidates = [t for t in [ts_chat, ts_file] if t is not None]
    last_active = max(candidates) if candidates else None

    from app.schemas.user import UserResponse
    return UserActivitySummary(
        user=UserResponse.model_validate(user),
        file_count=file_count,
        report_count=report_count,
        chat_session_count=chat_count,
        last_active=last_active,
    )
