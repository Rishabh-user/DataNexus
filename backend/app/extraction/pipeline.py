import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult
from app.extraction.chunker import TextChunker
from app.extraction.csv_extractor import CSVExtractor
from app.extraction.docx_extractor import DocxExtractor
from app.extraction.excel_extractor import ExcelExtractor
from app.extraction.image_extractor import ImageExtractor
from app.extraction.metadata import enrich_file_metadata
from app.extraction.pdf_extractor import PDFExtractor
from app.extraction.pptx_extractor import PptxExtractor
from app.models.document_chunk import DocumentChunk
from app.models.extracted_data import ExtractedData
from app.models.file import File
from app.utils.file_utils import get_file_extension

logger = get_logger(__name__)

EXTRACTORS: dict[str, BaseExtractor] = {}


def _get_extractors() -> dict[str, BaseExtractor]:
    global EXTRACTORS
    if not EXTRACTORS:
        all_extractors = [
            PDFExtractor(),
            ExcelExtractor(),
            CSVExtractor(),
            DocxExtractor(),
            PptxExtractor(),
            ImageExtractor(),
        ]
        for extractor in all_extractors:
            for ext in extractor.supported_extensions:
                EXTRACTORS[ext] = extractor
    return EXTRACTORS


def get_extractor(file_path: Path) -> BaseExtractor:
    ext = get_file_extension(str(file_path))
    extractors = _get_extractors()
    if ext not in extractors:
        raise ValueError(f"No extractor available for file type: {ext}")
    return extractors[ext]


async def process_file(db: AsyncSession, file_record: File) -> None:
    file_path = Path(file_record.storage_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_record.processing_status = "processing"
    await db.flush()

    try:
        # 1. Extract content
        extractor = get_extractor(file_path)
        result: ExtractionResult = await extractor.extract(file_path)

        # 2. Enrich metadata
        file_metadata = enrich_file_metadata(file_path, result)
        file_record.page_count = file_metadata.get("page_count")
        file_record.word_count = file_metadata.get("word_count")

        # 3. Store extracted structured data
        if result.text:
            extracted = ExtractedData(
                file_id=file_record.id,
                data_type="text",
                structured_data={"metadata": file_metadata},
                raw_text=result.text,
            )
            db.add(extracted)

        for table in result.tables:
            extracted = ExtractedData(
                file_id=file_record.id,
                data_type="table",
                structured_data={
                    "headers": table.headers,
                    "rows": table.rows,
                    "sheet_name": table.sheet_name,
                },
                source_page=table.page_number,
            )
            db.add(extracted)

        for kv in result.key_value_pairs:
            extracted = ExtractedData(
                file_id=file_record.id,
                data_type="key_value",
                structured_data=kv,
            )
            db.add(extracted)

        # 4. Chunk text for embeddings
        chunker = TextChunker()
        if result.pages:
            chunks = chunker.chunk_with_pages(result.pages)
        else:
            chunks = chunker.chunk_text(result.text, metadata={"filename": file_record.filename})

        for chunk_data in chunks:
            doc_chunk = DocumentChunk(
                file_id=file_record.id,
                chunk_index=chunk_data["chunk_index"],
                content=chunk_data["content"],
                metadata_json=chunk_data.get("metadata", {}),
                page_number=chunk_data.get("page_number"),
            )
            db.add(doc_chunk)

        file_record.processing_status = "completed"
        await db.flush()

        logger.info(
            "Processed file %s: %d chunks, %d tables",
            file_record.filename, len(chunks), len(result.tables),
        )

    except Exception as e:
        file_record.processing_status = "failed"
        file_record.error_message = str(e)
        await db.flush()
        logger.error("Failed to process file %s: %s", file_record.filename, str(e))
        raise
