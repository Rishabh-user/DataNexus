import aiofiles
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateFileError
from app.core.logging import get_logger
from app.models.file import File
from app.utils.file_utils import (
    compute_file_hash,
    generate_storage_path,
    get_file_type,
    get_mime_type,
)

logger = get_logger(__name__)


async def upload_file(db: AsyncSession, user_id: int, upload: UploadFile) -> File:
    from pathlib import Path

    filename = upload.filename or "unnamed"
    storage_path = generate_storage_path(user_id, filename)

    # Save file to disk
    async with aiofiles.open(storage_path, "wb") as f:
        content = await upload.read()
        await f.write(content)

    # Compute hash for deduplication
    file_hash = compute_file_hash(storage_path)

    # Check for duplicates
    result = await db.execute(
        select(File).where(File.user_id == user_id, File.file_hash == file_hash)
    )
    existing = result.scalar_one_or_none()
    if existing:
        # If the existing file's actual storage is gone (orphaned DB record), clean it up
        existing_path = Path(existing.storage_path) if existing.storage_path else None
        if existing_path and not existing_path.exists():
            logger.info("Cleaning up orphaned file record: %s (id=%d)", existing.filename, existing.id)
            await db.delete(existing)
            await db.flush()
        else:
            storage_path.unlink(missing_ok=True)
            raise DuplicateFileError(
                f"Duplicate file detected: '{filename}' matches existing file '{existing.filename}'"
            )

    file_record = File(
        user_id=user_id,
        filename=filename,
        file_type=get_file_type(filename),
        mime_type=get_mime_type(filename),
        source="upload",
        storage_path=str(storage_path),
        file_size=len(content),
        file_hash=file_hash,
        processing_status="pending",
    )
    db.add(file_record)
    await db.flush()

    logger.info("File uploaded: %s (id=%d)", filename, file_record.id)
    return file_record


async def get_user_files(
    db: AsyncSession, user_id: int, skip: int = 0, limit: int = 20, search: str | None = None
) -> tuple[list[File], int]:
    from sqlalchemy import func

    filters = [File.user_id == user_id]
    if search and search.strip():
        filters.append(File.filename.ilike(f"%{search.strip()}%"))

    count_result = await db.execute(
        select(func.count(File.id)).where(*filters)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(File)
        .where(*filters)
        .order_by(File.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    files = list(result.scalars().all())
    return files, total


async def get_file_by_id(db: AsyncSession, user_id: int, file_id: int) -> File:
    result = await db.execute(
        select(File).where(File.id == file_id, File.user_id == user_id)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    return file


async def delete_file(db: AsyncSession, user_id: int, file_id: int) -> None:
    file = await get_file_by_id(db, user_id, file_id)
    from pathlib import Path

    storage_path = Path(file.storage_path)
    if storage_path.exists():
        storage_path.unlink()

    await db.delete(file)
    await db.flush()
    logger.info("File deleted: %s (id=%d)", file.filename, file_id)
