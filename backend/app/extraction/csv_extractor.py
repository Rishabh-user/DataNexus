import asyncio
from pathlib import Path

import pandas as pd

from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult, TableData

logger = get_logger(__name__)


class CSVExtractor(BaseExtractor):
    @property
    def supported_extensions(self) -> list[str]:
        return [".csv"]

    async def extract(self, file_path: Path) -> ExtractionResult:
        return await asyncio.to_thread(self._extract_sync, file_path)

    def _extract_sync(self, file_path: Path) -> ExtractionResult:
        result = ExtractionResult()

        df = pd.read_csv(str(file_path), nrows=10000)
        headers = [str(col) for col in df.columns.tolist()]
        rows = [[str(val) for val in row] for row in df.values.tolist()]

        result.tables.append(TableData(headers=headers, rows=rows))

        result.metadata = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": headers,
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        }

        text_repr = " | ".join(headers) + "\n"
        for row in rows[:100]:  # Limit text representation
            text_repr += " | ".join(row) + "\n"

        if len(rows) > 100:
            text_repr += f"\n... and {len(rows) - 100} more rows"

        result.text = text_repr
        result.metadata["word_count"] = len(result.text.split())
        return result
