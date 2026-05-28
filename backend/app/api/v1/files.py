import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import PaginationParams
from app.core.logging import get_logger
from app.core.security import get_current_user, require_roles
from app.models.file import File
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.file import FileResponse, FileStatusResponse, FileUploadResponse
from app.services.file_service import (
    delete_file,
    get_file_accessible,
    get_file_by_id,
    get_user_files,
    upload_file,
)
from app.utils.validators import validate_upload_file

logger = get_logger(__name__)

router = APIRouter(prefix="/files", tags=["Files"])


async def _process_file_inline(file_id: int):
    """Process a single file directly without Celery."""
    from app.core.database import async_session_factory
    from app.extraction.pipeline import process_file

    try:
        async with async_session_factory() as db:
            result = await db.execute(select(File).where(File.id == file_id))
            file_record = result.scalar_one_or_none()
            if not file_record:
                logger.error("File not found for processing: %d", file_id)
                return

            file_record.processing_status = "processing"
            await db.commit()

            await process_file(db, file_record)
            await db.commit()
            logger.info("File processed successfully: %d - %s", file_id, file_record.filename)
    except Exception as e:
        logger.error("File processing failed for %d: %s", file_id, str(e))
        # Mark as failed
        try:
            async with async_session_factory() as db:
                result = await db.execute(select(File).where(File.id == file_id))
                file_record = result.scalar_one_or_none()
                if file_record:
                    file_record.processing_status = "failed"
                    file_record.error_message = str(e)[:500]
                    await db.commit()
        except Exception:
            pass


async def _process_files_sequential(file_ids: list[int]):
    """Process multiple files ONE AT A TIME to avoid SQLite locking.

    SQLite only supports one writer at a time. Running many background
    tasks in parallel causes 'database is locked' errors. This function
    processes files sequentially with a small pause between each.
    """
    for file_id in file_ids:
        await _process_file_inline(file_id)
        await asyncio.sleep(0.5)  # Brief pause between files


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN, UserRole.SUPERADMIN)),
):
    validate_upload_file(file)
    file_record = await upload_file(db, current_user.id, file)

    # Process directly using FastAPI BackgroundTasks (no Celery/Redis needed)
    background_tasks.add_task(_process_file_inline, file_record.id)

    return file_record


@router.get("", response_model=PaginatedResponse[FileResponse])
async def list_files(
    pagination: PaginationParams = Depends(),
    search: str | None = None,
    scope: str = "all",   # "all" = own + team files | "mine" = own only
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files, total = await get_user_files(
        db, current_user.id, pagination.skip, pagination.limit,
        search=search, scope=scope,
    )
    return PaginatedResponse(
        items=[FileResponse.from_db(f, current_user.id) for f in files],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        has_more=(pagination.skip + pagination.limit) < total,
    )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = await get_file_accessible(db, current_user.id, file_id)
    return FileResponse.from_db(file, current_user.id)


@router.get("/{file_id}/status", response_model=FileStatusResponse)
async def get_file_status(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = await get_file_accessible(db, current_user.id, file_id)
    return FileStatusResponse.model_validate(file)


@router.post("/process-all-pending")
async def process_all_pending(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN, UserRole.SUPERADMIN)),
):
    """Batch re-trigger processing for ALL pending/failed files.

    Files are processed sequentially (one at a time) to avoid SQLite
    'database is locked' errors that occur with parallel writes.
    """
    result = await db.execute(
        select(File).where(
            File.user_id == current_user.id,
            File.processing_status.in_(["pending", "failed"]),
        )
    )
    files = result.scalars().all()
    file_ids = [f.id for f in files]
    count = len(file_ids)

    if count > 0:
        # Single background task that processes all files sequentially
        background_tasks.add_task(_process_files_sequential, file_ids)

    return {"message": f"Processing {count} files in background (sequentially)", "count": count}


@router.post("/{file_id}/reprocess", response_model=FileStatusResponse)
async def reprocess_file(
    file_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN, UserRole.SUPERADMIN)),
):
    """Re-trigger processing for a stuck/failed file."""
    file_record = await get_file_by_id(db, current_user.id, file_id)
    file_record.processing_status = "pending"
    file_record.error_message = None
    await db.flush()
    background_tasks.add_task(_process_file_inline, file_record.id)
    return FileStatusResponse.model_validate(file_record)


@router.get("/{file_id}/extracted-data")
async def get_extracted_data(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View extracted data (text, tables, key-value pairs) for a processed file."""
    from app.models.extracted_data import ExtractedData
    from app.models.document_chunk import DocumentChunk

    # Verify file is accessible (own or team member)
    file_record = await get_file_accessible(db, current_user.id, file_id)

    # Get extracted data
    result = await db.execute(
        select(ExtractedData).where(ExtractedData.file_id == file_id)
    )
    extracted = result.scalars().all()

    # Get chunks
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.file_id == file_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()

    return {
        "file_id": file_id,
        "filename": file_record.filename,
        "processing_status": file_record.processing_status,
        "page_count": file_record.page_count,
        "word_count": file_record.word_count,
        "extracted_data": [
            {
                "id": ed.id,
                "data_type": ed.data_type,
                "raw_text": (ed.raw_text or "")[:2000],  # Truncate for response
                "structured_data": ed.structured_data,
                "source_page": ed.source_page,
            }
            for ed in extracted
        ],
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "content": c.content[:500],  # Truncate
                "page_number": c.page_number,
            }
            for c in chunks[:50]  # Max 50 chunks in response
        ],
        "total_chunks": len(chunks),
    }


@router.delete("/{file_id}", status_code=204)
async def remove_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN, UserRole.SUPERADMIN)),
):
    await delete_file(db, current_user.id, file_id)
