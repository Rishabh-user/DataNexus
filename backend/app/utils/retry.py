import asyncio
import functools
from typing import Any, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


def async_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            current_delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            "Retry %d/%d for %s: %s",
                            attempt + 1, max_retries, func.__name__, str(e),
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception

        return wrapper
    return decorator
