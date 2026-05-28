from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TableData:
    headers: list[str]
    rows: list[list[str]]
    page_number: int | None = None
    sheet_name: str | None = None


@dataclass
class ExtractionResult:
    text: str = ""
    tables: list[TableData] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    pages: list[dict] = field(default_factory=list)  # [{page: 1, text: "..."}, ...]
    key_value_pairs: list[dict] = field(default_factory=list)


class BaseExtractor(ABC):
    @abstractmethod
    async def extract(self, file_path: Path) -> ExtractionResult:
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        pass
