from pathlib import Path

from app.extraction.base import ExtractionResult


def enrich_file_metadata(file_path: Path, result: ExtractionResult) -> dict:
    stat = file_path.stat()
    base_meta = {
        "file_name": file_path.name,
        "file_size": stat.st_size,
        "file_extension": file_path.suffix.lower(),
    }
    base_meta.update(result.metadata)
    return base_meta
