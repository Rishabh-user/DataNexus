import asyncio
from pathlib import Path

from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult, TableData

logger = get_logger(__name__)


class PDFExtractor(BaseExtractor):
    @property
    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    async def extract(self, file_path: Path) -> ExtractionResult:
        return await asyncio.to_thread(self._extract_sync, file_path)

    def _extract_sync(self, file_path: Path) -> ExtractionResult:
        import fitz  # PyMuPDF

        result = ExtractionResult()
        all_text_parts = []

        doc = fitz.open(str(file_path))
        result.metadata = {
            "page_count": doc.page_count,
            "author": doc.metadata.get("author", ""),
            "title": doc.metadata.get("title", ""),
            "creation_date": doc.metadata.get("creationDate", ""),
        }

        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text("text")
            all_text_parts.append(text)
            result.pages.append({"page": page_num + 1, "text": text})

        doc.close()

        # Extract tables with pdfplumber
        try:
            import pdfplumber

            with pdfplumber.open(str(file_path)) as pdf:
                for i, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for table in tables:
                        if table and len(table) > 1:
                            headers = [str(cell or "") for cell in table[0]]
                            rows = [[str(cell or "") for cell in row] for row in table[1:]]
                            result.tables.append(
                                TableData(headers=headers, rows=rows, page_number=i + 1)
                            )
        except Exception as e:
            logger.warning("Table extraction failed for %s: %s", file_path, str(e))

        result.text = "\n\n".join(all_text_parts)
        result.metadata["word_count"] = len(result.text.split())

        # If no text found, try OCR
        if len(result.text.strip()) < 50:
            try:
                result = self._ocr_fallback(file_path, result)
            except Exception as e:
                logger.warning("OCR fallback failed: %s", str(e))

        return result

    def _ocr_fallback(self, file_path: Path, result: ExtractionResult) -> ExtractionResult:
        import fitz
        from PIL import Image
        import pytesseract
        import io

        doc = fitz.open(str(file_path))
        all_text_parts = []

        for page_num in range(doc.page_count):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img)
            all_text_parts.append(text)
            result.pages[page_num]["text"] = text

        doc.close()
        result.text = "\n\n".join(all_text_parts)
        result.metadata["ocr_applied"] = True
        result.metadata["word_count"] = len(result.text.split())
        return result
