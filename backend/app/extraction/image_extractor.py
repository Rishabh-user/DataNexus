import asyncio
from pathlib import Path

from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult

logger = get_logger(__name__)


class ImageExtractor(BaseExtractor):
    @property
    def supported_extensions(self) -> list[str]:
        return [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"]

    async def extract(self, file_path: Path) -> ExtractionResult:
        return await asyncio.to_thread(self._extract_sync, file_path)

    def _extract_sync(self, file_path: Path) -> ExtractionResult:
        from PIL import Image
        import pytesseract

        result = ExtractionResult()

        img = Image.open(str(file_path))
        result.metadata = {
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "mode": img.mode,
        }

        text = pytesseract.image_to_string(img)
        result.text = text.strip()
        result.metadata["word_count"] = len(result.text.split())
        result.metadata["ocr_applied"] = True

        return result
