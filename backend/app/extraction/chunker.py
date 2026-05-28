from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TextChunker:
    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk_text(self, text: str, metadata: dict | None = None) -> list[dict]:
        if not text.strip():
            return []

        chunks = []
        separators = ["\n\n", "\n", ". ", " "]
        raw_chunks = self._recursive_split(text, separators)

        for i, chunk_text in enumerate(raw_chunks):
            chunk_meta = dict(metadata or {})
            chunk_meta["chunk_index"] = i
            chunks.append({
                "content": chunk_text.strip(),
                "metadata": chunk_meta,
                "chunk_index": i,
            })

        return chunks

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        separator = separators[0] if separators else ""
        remaining_separators = separators[1:] if len(separators) > 1 else []

        if separator:
            parts = text.split(separator)
        else:
            # Character-level split as last resort
            chunks = []
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunks.append(text[i:i + self.chunk_size])
            return chunks

        chunks = []
        current_chunk = ""

        for part in parts:
            candidate = current_chunk + separator + part if current_chunk else part

            if len(candidate) <= self.chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                if len(part) > self.chunk_size and remaining_separators:
                    sub_chunks = self._recursive_split(part, remaining_separators)
                    chunks.extend(sub_chunks)
                else:
                    current_chunk = part

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def chunk_with_pages(self, pages: list[dict]) -> list[dict]:
        all_chunks = []
        global_index = 0

        for page_data in pages:
            page_num = page_data.get("page")
            text = page_data.get("text", "")
            page_chunks = self.chunk_text(
                text, metadata={"page_number": page_num}
            )
            for chunk in page_chunks:
                chunk["chunk_index"] = global_index
                chunk["page_number"] = page_num
                global_index += 1
                all_chunks.append(chunk)

        return all_chunks
