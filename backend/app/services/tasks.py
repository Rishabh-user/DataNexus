from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_sync_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings

    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    return Session()


@celery_app.task(
    name="app.services.tasks.process_file_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_file_task(self, file_id: int):
    import asyncio
    from app.core.database import async_session_factory
    from app.extraction.pipeline import process_file
    from app.ai.embeddings import generate_embeddings_batch
    from app.ai.vector_store import bulk_store_embeddings
    from app.models.file import File
    from app.models.document_chunk import DocumentChunk
    from sqlalchemy import select

    async def _process():
        async with async_session_factory() as db:
            try:
                result = await db.execute(select(File).where(File.id == file_id))
                file_record = result.scalar_one_or_none()
                if not file_record:
                    logger.error("File not found: %d", file_id)
                    return

                # Process file (extract + chunk)
                await process_file(db, file_record)

                # Generate embeddings for chunks
                chunks_result = await db.execute(
                    select(DocumentChunk)
                    .where(DocumentChunk.file_id == file_id)
                    .order_by(DocumentChunk.chunk_index)
                )
                chunks = list(chunks_result.scalars().all())

                if chunks:
                    texts = [c.content for c in chunks]
                    embeddings = await generate_embeddings_batch(texts)
                    chunk_ids = [c.id for c in chunks]
                    await bulk_store_embeddings(db, chunk_ids, embeddings)

                await db.commit()
                logger.info("File processing complete: %d", file_id)

            except Exception as e:
                await db.rollback()
                logger.error("File processing failed: %d - %s", file_id, str(e))
                raise self.retry(exc=e)

    asyncio.run(_process())


@celery_app.task(
    name="app.services.tasks.sync_onedrive_task",
    bind=True,
    max_retries=3,
)
def sync_onedrive_task(self, user_id: int, folder_id: str | None = None):
    import asyncio
    from app.core.database import async_session_factory
    from app.integrations.onedrive.sync import OneDriveSyncService

    async def _sync():
        async with async_session_factory() as db:
            try:
                sync_service = OneDriveSyncService(db, user_id)
                result = await sync_service.sync_folder(folder_id)
                await db.commit()

                # Trigger processing for synced files
                from app.models.file import File
                from sqlalchemy import select

                async with async_session_factory() as db2:
                    pending = await db2.execute(
                        select(File).where(
                            File.user_id == user_id,
                            File.processing_status == "pending",
                        )
                    )
                    for file in pending.scalars().all():
                        process_file_task.delay(file.id)

                return result

            except Exception as e:
                await db.rollback()
                logger.error("OneDrive sync failed for user %d: %s", user_id, str(e))
                raise self.retry(exc=e)

    return asyncio.run(_sync())


@celery_app.task(name="app.services.tasks.generate_report_task", bind=True, max_retries=2)
def generate_report_task(self, user_id: int, title: str, prompt: str, include_charts: bool = True):
    import asyncio
    from app.core.database import async_session_factory
    from app.services.report_service import generate_report

    async def _generate():
        async with async_session_factory() as db:
            try:
                report = await generate_report(db, user_id, title, prompt, include_charts)
                await db.commit()
                return report.id
            except Exception as e:
                await db.rollback()
                logger.error("Report generation failed: %s", str(e))
                raise self.retry(exc=e)

    return asyncio.run(_generate())


@celery_app.task(name="app.services.tasks.generate_embeddings_task")
def generate_embeddings_task(file_id: int):
    import asyncio
    from app.core.database import async_session_factory
    from app.ai.embeddings import generate_embeddings_batch
    from app.ai.vector_store import bulk_store_embeddings
    from app.models.document_chunk import DocumentChunk
    from sqlalchemy import select

    async def _generate():
        async with async_session_factory() as db:
            chunks_result = await db.execute(
                select(DocumentChunk)
                .where(
                    DocumentChunk.file_id == file_id,
                    DocumentChunk.embedding.is_(None),
                )
                .order_by(DocumentChunk.chunk_index)
            )
            chunks = list(chunks_result.scalars().all())

            if not chunks:
                return

            texts = [c.content for c in chunks]
            embeddings = await generate_embeddings_batch(texts)
            chunk_ids = [c.id for c in chunks]
            await bulk_store_embeddings(db, chunk_ids, embeddings)
            await db.commit()
            logger.info("Embeddings generated for file %d: %d chunks", file_id, len(chunks))

    asyncio.run(_generate())
