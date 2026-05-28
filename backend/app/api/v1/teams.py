"""Teams API — create teams, manage members, share document visibility."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.team import (
    TeamAddMember,
    TeamCreate,
    TeamDetailResponse,
    TeamMemberInfo,
    TeamResponse,
    TeamUpdate,
)
from app.services.team_service import (
    add_team_member,
    create_team,
    delete_team,
    get_team_detail,
    get_user_teams,
    leave_team,
    remove_team_member,
    update_team,
)

router = APIRouter(prefix="/teams", tags=["Teams"])

# All team actions require at least analyst-level access
_analyst_plus = Depends(
    require_roles(UserRole.ANALYST, UserRole.ADMIN, UserRole.SUPERADMIN)
)


@router.get("", response_model=list[TeamResponse])
async def list_teams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all teams the current user belongs to."""
    teams = await get_user_teams(db, current_user.id)
    return [TeamResponse(**t) for t in teams]


@router.post("", response_model=TeamResponse, status_code=201)
async def create_new_team(
    data: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = _analyst_plus,
):
    """Create a new team. Creator becomes the team owner."""
    team = await create_team(db, current_user.id, data)
    return TeamResponse(**team)


@router.get("/{team_id}", response_model=TeamDetailResponse)
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get team details with full member list. Only accessible to team members."""
    detail = await get_team_detail(db, current_user.id, team_id)
    return TeamDetailResponse(**detail)


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team_info(
    team_id: int,
    data: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = _analyst_plus,
):
    """Update team name or description. Owner only."""
    await update_team(db, current_user.id, team_id, data)
    detail = await get_team_detail(db, current_user.id, team_id)
    return TeamResponse(**detail)


@router.delete("/{team_id}", status_code=204)
async def delete_team_endpoint(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = _analyst_plus,
):
    """Delete the team permanently. Owner only."""
    await delete_team(db, current_user.id, team_id)


@router.post("/{team_id}/members", response_model=TeamMemberInfo, status_code=201)
async def add_member(
    team_id: int,
    data: TeamAddMember,
    db: AsyncSession = Depends(get_db),
    current_user: User = _analyst_plus,
):
    """Add a user to the team by email address. Owner only."""
    member = await add_team_member(db, current_user.id, team_id, data.email)
    return TeamMemberInfo(**member)


@router.delete("/{team_id}/members/{target_user_id}", status_code=204)
async def remove_member(
    team_id: int,
    target_user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = _analyst_plus,
):
    """Remove a member from the team. Owner only."""
    await remove_team_member(db, current_user.id, team_id, target_user_id)


@router.post("/{team_id}/leave", status_code=204)
async def leave_team_endpoint(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Leave a team you are a member of."""
    await leave_team(db, current_user.id, team_id)
