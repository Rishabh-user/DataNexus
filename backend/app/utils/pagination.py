from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


async def paginate(
    db: AsyncSession,
    query: Select,
    skip: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    result = await db.execute(query.offset(skip).limit(limit))
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total,
    }
