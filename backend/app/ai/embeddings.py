"""Embeddings — lightweight local TF-IDF based.

Anthropic/Claude does not provide an embeddings API, so we use a simple
local approach that works on SQLite without pgvector.  For production
with PostgreSQL you can swap in any embedding provider.
"""

import hashlib
import math
import re
from collections import Counter

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ---- Simple hash-based embedding (deterministic, fast, no GPU) ----
# This creates a fixed-dimension vector from text using hashing trick.
# It's NOT semantic — it's keyword-based. Good enough for SQLite local dev.
# For production, plug in a real embedding model here.

DIMENSION = settings.embedding_dimension


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [w for w in text.split() if len(w) > 1]


def _hash_embed(text: str, dim: int = DIMENSION) -> list[float]:
    """Create a deterministic embedding vector using the hashing trick."""
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * dim

    vec = [0.0] * dim
    counts = Counter(tokens)
    total = len(tokens)

    for token, count in counts.items():
        # Hash token to get a bucket index
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        tf = count / total
        vec[idx] += sign * tf

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]

    return vec


async def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for a single text."""
    text = text.replace("\n", " ").strip()
    if not text:
        return [0.0] * DIMENSION
    return _hash_embed(text)


async def generate_embeddings_batch(
    texts: list[str], batch_size: int = 100
) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    results = []
    for i, text in enumerate(texts):
        results.append(await generate_embedding(text))
        if (i + 1) % 100 == 0:
            logger.debug("Generated embeddings: %d/%d", i + 1, len(texts))
    return results
