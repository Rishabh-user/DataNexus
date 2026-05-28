from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.vector_store import similarity_search
from app.core.config import settings
from app.core.logging import get_logger
from app.models.extracted_data import ExtractedData
from app.models.file import File

logger = get_logger(__name__)


async def retrieve_context(
    db: AsyncSession,
    query: str,
    user_id: int,
    top_k: int | None = None,
    file_type_filter: str | None = None,
) -> dict:
    # 1. Semantic search over document chunks
    semantic_results = await similarity_search(
        db=db,
        query=query,
        user_id=user_id,
        top_k=top_k or settings.top_k_results,
        file_type_filter=file_type_filter,
    )

    # 2. Build context string from semantic results
    context_parts = []
    sources = []
    for result in semantic_results:
        source_ref = f"[{result['filename']}"
        if result["page_number"]:
            source_ref += f", page {result['page_number']}"
        source_ref += "]"

        context_parts.append(f"{source_ref}:\n{result['content']}")
        sources.append(result)

    # 3. Get structured data from matched files
    file_ids = list({r["file_id"] for r in semantic_results})
    structured_data = ""
    if file_ids:
        result = await db.execute(
            select(ExtractedData).where(
                ExtractedData.file_id.in_(file_ids),
                ExtractedData.data_type.in_(["table", "key_value"]),
            )
        )
        extracted_items = result.scalars().all()

        structured_parts = []
        for item in extracted_items:
            if item.data_type == "table":
                data = item.structured_data
                headers = data.get("headers", [])
                rows = data.get("rows", [])[:10]
                table_str = " | ".join(headers) + "\n"
                for row in rows:
                    table_str += " | ".join(str(v) for v in row) + "\n"
                structured_parts.append(table_str)
            elif item.data_type == "key_value":
                for k, v in item.structured_data.items():
                    structured_parts.append(f"{k}: {v}")

        structured_data = "\n".join(structured_parts)

    return {
        "context": "\n\n".join(context_parts),
        "structured_data": structured_data,
        "sources": sources,
    }
