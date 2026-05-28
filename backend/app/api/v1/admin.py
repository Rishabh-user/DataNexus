"""Admin router — user management and system stats (admin/superadmin only)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.models.user import User, UserRole
from app.schemas.user import (
    AdminUserCreate,
    AdminUserUpdate,
    SystemStats,
    UserActivitySummary,
    UserListResponse,
    UserListItem,
    UserResponse,
)
from app.services.user_service import (
    create_user_by_admin,
    delete_user_by_admin,
    get_system_stats,
    get_user_activity,
    get_user_by_id_admin,
    list_all_users,
    toggle_user_active,
    update_user_by_admin,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

# Reusable dependencies
_admin_dep  = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))
_super_dep  = Depends(require_roles(UserRole.SUPERADMIN))


# ─── System stats ─────────────────────────────────────────────────────────────

@router.get("/stats", response_model=SystemStats)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = _admin_dep,
):
    """Platform-wide statistics (admin+)."""
    return await get_system_stats(db)


# ─── User list ────────────────────────────────────────────────────────────────

@router.get("/users", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Search by name or email"),
    role: str | None = Query(None, description="Filter by role"),
    active: bool | None = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = _admin_dep,
):
    """List all users with optional filters (admin+)."""
    users, total = await list_all_users(db, skip, limit, search, role, active)
    return UserListResponse(
        items=[UserListItem.model_validate(u) for u in users],
        total=total,
        skip=skip,
        limit=limit,
        has_more=(skip + limit) < total,
    )


# ─── Create user ──────────────────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    data: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = _admin_dep,
):
    """Create a new user (admin+). Admins can only assign analyst/viewer roles."""
    user = await create_user_by_admin(db, data, current_user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ─── Get single user ──────────────────────────────────────────────────────────

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = _admin_dep,
):
    """Get any user by ID (admin+)."""
    user = await get_user_by_id_admin(db, user_id)
    return UserResponse.model_validate(user)


# ─── Update user ──────────────────────────────────────────────────────────────

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = _admin_dep,
):
    """Update a user's profile or role (admin+). Role assignment is permission-controlled."""
    user = await update_user_by_admin(db, user_id, data, current_user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ─── Toggle active ────────────────────────────────────────────────────────────

@router.patch("/users/{user_id}/toggle-active", response_model=UserResponse)
async def toggle_active(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = _admin_dep,
):
    """Activate or deactivate a user account (admin+)."""
    user = await toggle_user_active(db, user_id, current_user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ─── Delete user ──────────────────────────────────────────────────────────────

@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = _super_dep,
):
    """Permanently delete a user and all their data (superadmin only)."""
    await delete_user_by_admin(db, user_id, current_user)
    await db.commit()


# ─── User activity summary ────────────────────────────────────────────────────

@router.get("/users/{user_id}/activity", response_model=UserActivitySummary)
async def user_activity(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = _admin_dep,
):
    """Get file/report/chat counts for a specific user (admin+)."""
    return await get_user_activity(db, user_id)
