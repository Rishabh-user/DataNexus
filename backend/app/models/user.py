from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ─── Role constants ───────────────────────────────────────────────────────────
class UserRole:
    SUPERADMIN = "superadmin"
    ADMIN      = "admin"
    ANALYST    = "analyst"
    VIEWER     = "viewer"

    # Ordered hierarchy: higher index = more permissions
    HIERARCHY = ["viewer", "analyst", "admin", "superadmin"]

    # Roles that can manage other users
    ADMIN_ROLES = {"superadmin", "admin"}

    # All valid role values
    ALL = {"superadmin", "admin", "analyst", "viewer"}

    @classmethod
    def rank(cls, role: str) -> int:
        try:
            return cls.HIERARCHY.index(role)
        except ValueError:
            return cls.HIERARCHY.index("analyst")   # legacy "user" → analyst level

    @classmethod
    def can_assign(cls, assigner_role: str, target_role: str) -> bool:
        """superadmin can assign any role; admin can only assign analyst/viewer."""
        if assigner_role == cls.SUPERADMIN:
            return True
        if assigner_role == cls.ADMIN:
            return target_role in {cls.ANALYST, cls.VIEWER}
        return False


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    files: Mapped[list["File"]] = relationship(back_populates="user", lazy="noload")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user", lazy="noload")
    onedrive_token: Mapped["OneDriveToken | None"] = relationship(back_populates="user", uselist=False, lazy="noload")
    reports: Mapped[list["Report"]] = relationship(back_populates="user", lazy="noload")
    owned_teams: Mapped[list["Team"]] = relationship(
        foreign_keys="[Team.created_by]", back_populates="creator", lazy="noload"
    )
    team_memberships: Mapped[list["TeamMember"]] = relationship(
        back_populates="user", lazy="noload"
    )
