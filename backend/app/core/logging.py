import logging
import sys
from typing import Any

from app.core.config import settings


def setup_logging() -> None:
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    )

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.debug else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class LoggerMixin:
    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(self.__class__.__qualname__)
