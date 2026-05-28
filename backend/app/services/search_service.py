from sqlalchemy import select, text
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
    # Use raw SQL for cross-DB compatibility
    params = {"user_id": user_id, "search_term": f"%{query}%"}

    type_clause = ""
    if data_type:
        type_clause = "AND ed.data_type = :data_type"
        params["data_type"] = data_type

    sql = text(f"""
        SELECT ed.id, ed.file_id, ed.data_type, ed.raw_text,
               ed.structured_data, ed.source_page, f.filename
        FROM extracted_data ed
        JOIN files f ON ed.file_id = f.id
        WHERE f.user_id = :user_id
            AND (ed.raw_text LIKE :search_term)
            {type_clause}
        LIMIT 20
    """)

    result = await db.execute(sql, params)
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
