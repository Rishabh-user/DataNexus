"""Team management service — create teams, manage members, share document visibility."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.team import Team, TeamMember, TeamMemberRole
from app.models.user import User
from app.schemas.team import TeamCreate, TeamUpdate

logger = get_logger(__name__)


# ─── Read ──────────────────────────────────────────────────────────────────────

async def get_user_teams(db: AsyncSession, user_id: int) -> list[dict]:
    """Return all teams the user belongs to, with member count and their role."""
    result = await db.execute(
        select(TeamMember)
        .options(
            selectinload(TeamMember.team).selectinload(Team.members)
        )
        .where(TeamMember.user_id == user_id)
        .order_by(TeamMember.joined_at.desc())
    )
    memberships = result.scalars().all()

    teams = []
    for m in memberships:
        team = m.team
        teams.append({
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "created_by": team.created_by,
            "created_at": team.created_at,
            "updated_at": team.updated_at,
            "member_count": len(team.members),
            "your_role": m.role,
        })
    return teams


async def get_team_detail(db: AsyncSession, user_id: int, team_id: int) -> dict:
    """Return team detail with member list. Caller must be a member."""
    # Verify membership
    mem_result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
        )
    )
    membership = mem_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this team",
        )

    # Fetch team with all members + their user data
    result = await db.execute(
        select(Team)
        .options(
            selectinload(Team.members).selectinload(TeamMember.user)
        )
        .where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    members = [
        {
            "user_id": m.user_id,
            "full_name": m.user.full_name if m.user else "Unknown",
            "email": m.user.email if m.user else "",
            "role": m.role,
            "joined_at": m.joined_at,
        }
        for m in team.members
        if m.user
    ]

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "created_by": team.created_by,
        "created_at": team.created_at,
        "updated_at": team.updated_at,
        "member_count": len(team.members),
        "your_role": membership.role,
        "members": members,
    }


async def _get_team_as_owner(db: AsyncSession, user_id: int, team_id: int) -> Team:
    """Fetch team and verify caller is the owner."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    mem = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.role == TeamMemberRole.OWNER,
        )
    )
    if not mem.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team owner can perform this action",
        )
    return team


# ─── Write ─────────────────────────────────────────────────────────────────────

async def create_team(db: AsyncSession, user_id: int, data: TeamCreate) -> dict:
    """Create a new team and add creator as owner."""
    team = Team(
        name=data.name.strip(),
        description=data.description,
        created_by=user_id,
    )
    db.add(team)
    await db.flush()  # get team.id

    # Add creator as owner
    db.add(TeamMember(
        team_id=team.id,
        user_id=user_id,
        role=TeamMemberRole.OWNER,
    ))
    await db.flush()
    logger.info("Team created: '%s' (id=%d) by user %d", team.name, team.id, user_id)

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "created_by": team.created_by,
        "created_at": team.created_at,
        "updated_at": team.updated_at,
        "member_count": 1,
        "your_role": TeamMemberRole.OWNER,
    }


async def update_team(
    db: AsyncSession, user_id: int, team_id: int, data: TeamUpdate
) -> dict:
    """Update team name/description. Owner only."""
    team = await _get_team_as_owner(db, user_id, team_id)
    if data.name is not None:
        team.name = data.name.strip()
    if data.description is not None:
        team.description = data.description
    await db.flush()
    logger.info("Team updated: id=%d by user %d", team_id, user_id)
    return {"id": team.id, "name": team.name, "description": team.description}


async def delete_team(db: AsyncSession, user_id: int, team_id: int) -> None:
    """Delete team entirely. Owner only."""
    team = await _get_team_as_owner(db, user_id, team_id)
    await db.delete(team)
    await db.flush()
    logger.info("Team deleted: id=%d by user %d", team_id, user_id)


# ─── Members ───────────────────────────────────────────────────────────────────

async def add_team_member(
    db: AsyncSession, user_id: int, team_id: int, email: str
) -> dict:
    """Add a user to the team by email. Owner only."""
    await _get_team_as_owner(db, user_id, team_id)

    # Look up target user
    result = await db.execute(select(User).where(User.email == email.strip().lower()))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user found with email: {email}",
        )
    if not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user account is inactive",
        )

    # Check already a member
    existing = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == target.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{target.full_name} is already a member of this team",
        )

    member = TeamMember(
        team_id=team_id,
        user_id=target.id,
        role=TeamMemberRole.MEMBER,
    )
    db.add(member)
    await db.flush()
    logger.info(
        "Added user %d (%s) to team %d by user %d",
        target.id, target.email, team_id, user_id,
    )
    return {
        "user_id": target.id,
        "full_name": target.full_name,
        "email": target.email,
        "role": TeamMemberRole.MEMBER,
        "joined_at": member.joined_at,
    }


async def remove_team_member(
    db: AsyncSession, user_id: int, team_id: int, target_user_id: int
) -> None:
    """Remove a member from the team. Owner only. Cannot remove self (use leave_team)."""
    await _get_team_as_owner(db, user_id, team_id)

    if target_user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the leave endpoint to remove yourself from a team",
        )

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == target_user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this team",
        )
    if member.role == TeamMemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the team owner",
        )

    await db.delete(member)
    await db.flush()
    logger.info("Removed user %d from team %d by user %d", target_user_id, team_id, user_id)


async def leave_team(db: AsyncSession, user_id: int, team_id: int) -> None:
    """Leave a team. Owners must delete the team instead."""
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this team",
        )
    if member.role == TeamMemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team owners cannot leave. Delete the team or transfer ownership first.",
        )

    await db.delete(member)
    await db.flush()
    logger.info("User %d left team %d", user_id, team_id)


# ─── Helper (used by file_service) ─────────────────────────────────────────────

async def get_teammate_ids(db: AsyncSession, user_id: int) -> set[int]:
    """Return all user IDs that share at least one team with the given user (including self)."""
    result = await db.execute(
        select(TeamMember.user_id)
        .where(
            TeamMember.team_id.in_(
                select(TeamMember.team_id).where(TeamMember.user_id == user_id)
            )
        )
        .distinct()
    )
    ids = {row[0] for row in result.all()}
    ids.add(user_id)  # always include self
    return ids
