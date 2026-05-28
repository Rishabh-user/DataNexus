from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.vector_store import similarity_search
from app.core.logging import get_logger
from app.models.extracted_data import ExtractedData
from app.models.file import File
from app.schemas.search import SearchResult

logger = get_logger(__name__)


async def semantic_search(
    db: AsyncSession,
    user_id: int,
    query: str,
    top_k: int = 5,
    file_type_filter: str | None = None,
) -> list[SearchResult]:
    results = await similarity_search(
        db=db,
        query=query,
        user_id=user_id,
        top_k=top_k,
        file_type_filter=file_type_filter,
    )

    return [
        SearchResult(
            file_id=r["file_id"],
            filename=r["filename"],
            content=r["content"],
            page_number=r.get("page_number"),
            relevance_score=r["relevance_score"],
            metadata=r.get("metadata"),
        )
        for r in results
    ]


async def structured_search(
    db: AsyncSession,
    user_id: int,
    query: str,
    data_type: str | None = None,
) -> list[SearchResult]:
    # Resolve visible user IDs (own + team members) — avoids raw SQL IN limitation
    from app.ai.vector_store import _get_visible_user_ids
    visible_ids = await _get_visible_user_ids(db, user_id)

    filters = [
        File.user_id.in_(visible_ids),
        ExtractedData.raw_text.ilike(f"%{query}%"),
    ]
    if data_type:
        filters.append(ExtractedData.data_type == data_type)

    stmt = (
        select(
            ExtractedData.id,
            ExtractedData.file_id,
            ExtractedData.data_type,
            ExtractedData.raw_text,
            ExtractedData.structured_data,
            ExtractedData.source_page,
            File.filename,
        )
        .join(File, ExtractedData.file_id == File.id)
        .where(*filters)
        .limit(20)
    )
    result = await db.execute(stmt)
    rows = result.fetchall()

    return [
        SearchResult(
            file_id=row.file_id,
            filename=row.filename,
            content=row.raw_text[:500] if row.raw_text else str(row.structured_data)[:500],
            page_number=row.source_page,
            relevance_score=1.0,
            data_type=row.data_type,
        )
        for row in rows
    ]
