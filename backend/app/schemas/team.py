from datetime import datetime

from pydantic import BaseModel, field_validator


class TeamCreate(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Team name cannot be empty")
        if len(v) > 100:
            raise ValueError("Team name must be 100 characters or less")
        return v


class TeamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class TeamAddMember(BaseModel):
    email: str


class TeamMemberInfo(BaseModel):
    user_id: int
    full_name: str
    email: str
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class TeamResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    your_role: str = "member"

    model_config = {"from_attributes": True}


class TeamDetailResponse(TeamResponse):
    members: list[TeamMemberInfo] = []
