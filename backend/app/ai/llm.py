"""LLM layer — uses Anthropic Claude API exclusively."""

import asyncio
import random

import anthropic

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_claude_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(
            api_key=settings.claude_api_key,
            max_retries=0,   # Disable SDK retries — we handle them below with backoff
            timeout=120.0,
        )
    return _client


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    system: str | None = None,
) -> str:
    """Send messages to Claude and return the text response.

    Handles retries for overloaded (529) errors with exponential backoff.
    """
    client = get_claude_client()

    # Claude API: system prompt is a separate parameter, not in messages
    system_prompt = system
    claude_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        else:
            claude_messages.append({"role": msg["role"], "content": msg["content"]})

    # Claude requires at least one user message
    if not claude_messages:
        claude_messages = [{"role": "user", "content": "Hello"}]

    kwargs = {
        "model": model or settings.claude_model,
        "max_tokens": max_tokens,
        "messages": claude_messages,
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    if temperature is not None:
        kwargs["temperature"] = temperature

    last_error = None
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            response = await client.messages.create(**kwargs)

            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
            return "".join(text_parts)

        except anthropic.OverloadedError as e:
            last_error = e
            # Exponential backoff with jitter: ~5s, 11s, 23s, 47s, 60s
            wait = min(5 * (2 ** attempt) + random.uniform(0, 3), 60)
            logger.warning(
                "Claude API overloaded (attempt %d/%d), retrying in %.1fs...",
                attempt + 1, max_attempts, wait,
            )
            await asyncio.sleep(wait)

        except anthropic.RateLimitError as e:
            last_error = e
            # Longer backoff for rate limits: ~10s, 22s, 46s, 60s, 60s
            wait = min(10 * (2 ** attempt) + random.uniform(0, 3), 60)
            logger.warning(
                "Claude API rate limited (attempt %d/%d), retrying in %.1fs...",
                attempt + 1, max_attempts, wait,
            )
            await asyncio.sleep(wait)

        except anthropic.APIStatusError as e:
            # Auth errors, bad requests — don't retry
            logger.error("Claude API error: %s", str(e))
            raise

    raise last_error  # type: ignore[misc]


async def generate_chat_response(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> str:
    """Convenience: system + user message → Claude response."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return await chat_completion(messages, model=model)


async def generate_with_history(
    system_prompt: str,
    chat_history: list[dict],
    user_message: str,
    model: str | None = None,
) -> str:
    """Send with conversation history."""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": user_message})
    return await chat_completion(messages, model=model)
