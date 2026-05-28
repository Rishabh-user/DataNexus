"""Vector store — SQLite-compatible text search with optional embedding similarity."""

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import generate_embedding
from app.core.config import settings
from app.core.logging import get_logger
from app.models.document_chunk import DocumentChunk
from app.models.file import File

logger = get_logger(__name__)

# Common English stopwords to exclude from search
_STOPWORDS = {
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "of", "for",
    "and", "or", "but", "not", "be", "are", "was", "were", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "this", "that", "these",
    "those", "with", "from", "into", "about", "what", "which", "who",
    "whom", "how", "when", "where", "why", "all", "each", "every",
    "both", "few", "more", "most", "some", "any", "no", "nor", "too",
    "very", "just", "also", "than", "then", "now", "here", "there",
    "its", "our", "your", "his", "her", "my", "their", "me", "you",
    "him", "she", "they", "we", "us", "them", "i", "am",
    # Common filler words in user queries (keep domain words like "report", "list")
    "please", "make", "give", "get", "tell",
    "prepare", "write", "provide",
    "help", "need", "want", "like", "know", "look", "see", "use",
}


def _split_compound_word(word: str) -> list[str]:
    """Split camelCase, PascalCase, and concatenated words.

    'BankAccount' → ['bank', 'account']
    'bankaccount' → ['bank', 'account']
    'TEMPERATURE' → ['temperature']
    'breaf'       → ['breaf']  (no split for short/unknown words)
    """
    import re
    # CamelCase / PascalCase split: "BankAccount" → ["Bank", "Account"]
    parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)', word)
    if len(parts) > 1:
        filtered = [p.lower() for p in parts if len(p) > 2]
        return filtered if filtered else [word.lower()]

    # For all-lowercase words, only split if we recognise known sub-words.
    # This avoids nonsense splits like "breaf" → ["bre","af"].
    _KNOWN_WORDS = {
        "bank", "account", "report", "data", "file", "name", "code",
        "list", "sale", "sales", "purchase", "order", "orders",
        "item", "items", "stock", "price", "date", "time", "number",
        "balance", "amount", "total", "customer", "vendor", "product",
        "invoice", "payment", "credit", "debit", "entry", "ledger",
        "sheet", "master", "detail", "head", "line", "type", "status",
        "marine", "equipment", "material", "work", "cost", "value",
        "weight", "unit", "rate", "quantity", "description", "project",
        "company", "branch", "address", "phone", "email", "country",
        "state", "city", "employee", "department", "salary", "tax",
        "profit", "loss", "asset", "income", "expense", "budget",
        "category", "group", "class", "level", "grade", "mark",
    }
    w = word.lower()
    for i in range(3, len(w) - 2):
        left, right = w[:i], w[i:]
        if left in _KNOWN_WORDS and right in _KNOWN_WORDS:
            return [left, right]

    return [w]


def _extract_search_terms(query: str) -> list[str]:
    """Extract meaningful search terms from a user query, removing stopwords.

    Handles:
    - Stopword removal
    - CamelCase splitting: "BankAccount" → ["bank", "account"]
    - Concatenated word splitting: "bankaccount" → ["bank", "account"]
    - Quoted phrase preservation
    """
    import re

    # Extract quoted phrases first
    quoted_phrases = re.findall(r'"([^"]+)"', query)

    # Remove quotes and special chars
    cleaned = query.replace('"', ' ').replace("'", ' ').replace(':', ' ')
    raw_terms = [t.strip() for t in cleaned.split() if len(t.strip()) > 2]

    # Process each term
    meaningful = []
    seen = set()
    for term in raw_terms:
        lower = term.lower()
        if lower in _STOPWORDS:
            continue
        # Try splitting compound words
        parts = _split_compound_word(term)
        # If split produced multiple parts, add parts AND the original
        if len(parts) > 1:
            for p in parts:
                if p not in seen and p not in _STOPWORDS and len(p) > 2:
                    meaningful.append(p)
                    seen.add(p)
            # Also keep original (e.g. "bankaccount") for exact matches
            if lower not in seen and len(lower) > 2:
                meaningful.append(lower)
                seen.add(lower)
        else:
            p = parts[0] if parts else lower
            if p not in seen and p not in _STOPWORDS and len(p) > 2:
                meaningful.append(p)
                seen.add(p)

    # Add quoted phrases as-is (for exact matching)
    for phrase in quoted_phrases:
        p = phrase.strip().lower()
        if p and p not in seen:
            meaningful.append(p)
            seen.add(p)

    # If all terms were stopwords, fall back to longest terms from original
    if not meaningful and raw_terms:
        meaningful = sorted([t.lower() for t in raw_terms], key=len, reverse=True)[:5]

    return meaningful[:15]


async def similarity_search(
    db: AsyncSession,
    query: str,
    user_id: int,
    top_k: int | None = None,
    file_type_filter: str | None = None,
) -> list[dict]:
    """Search document chunks using keyword matching (SQLite compatible).

    Strategy: query each search term separately (max 50 rows each) to ensure
    rare-but-important terms (like "bank") aren't drowned out by common ones
    (like "data").  Then score & rank in Python.
    """
    top_k = top_k or settings.top_k_results

    # Extract meaningful search terms
    terms = _extract_search_terms(query)
    logger.info("Search terms for '%s': %s", query[:80], terms)

    if not terms:
        return []

    # ----- gather candidates per term (avoids SQL LIMIT drowning) -----
    base_filters = [
        File.user_id == user_id,
        File.processing_status == "completed",
    ]
    if file_type_filter:
        base_filters.append(File.file_type == file_type_filter)

    seen_ids: set[int] = set()
    all_rows = []
    PER_TERM_LIMIT = 50  # enough per term to get diversity

    for term in terms:
        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.file_id,
                DocumentChunk.content,
                DocumentChunk.page_number,
                DocumentChunk.metadata_json,
                DocumentChunk.chunk_index,
                File.filename,
                File.file_type,
            )
            .join(File, DocumentChunk.file_id == File.id)
            .where(*base_filters)
            .where(DocumentChunk.content.ilike(f"%{term}%"))
            .limit(PER_TERM_LIMIT)
        )
        result = await db.execute(stmt)
        for row in result.fetchall():
            if row.id not in seen_ids:
                seen_ids.add(row.id)
                all_rows.append(row)

    logger.info("Collected %d unique candidate chunks for %d terms", len(all_rows), len(terms))

    # ----- compute term document frequency for IDF-like weighting -----
    term_doc_freq: dict[str, int] = {t: 0 for t in terms}
    for row in all_rows:
        cl = (row.content or "").lower()
        for t in terms:
            if t in cl:
                term_doc_freq[t] += 1
    total_docs = max(len(all_rows), 1)

    # ----- score every candidate -----
    query_lower = query.lower()
    scored_results = []
    for row in all_rows:
        content_lower = (row.content or "").lower()
        matched_terms = sum(1 for t in terms if t in content_lower)
        if matched_terms == 0:
            continue

        # IDF-weighted score: rare terms count more than common ones
        score = 0.0
        for t in terms:
            if t in content_lower:
                df = term_doc_freq.get(t, 1)
                idf = 1.0 / (1.0 + (df / total_docs))
                # Count occurrences (term frequency) capped at 5
                tf = min(content_lower.count(t), 5)
                score += idf * (1.0 + 0.2 * (tf - 1))

        # Normalize by number of terms
        score /= max(len(terms), 1)

        # Bonus for exact phrase match (or large substring)
        if query_lower[:60] in content_lower:
            score += 1.5

        # Bonus for matching multiple distinct terms (diversity)
        if matched_terms >= 3:
            score += 0.4
        elif matched_terms >= 2:
            score += 0.2

        # Bonus: filename matches a search term (strong relevance signal)
        fname_lower = (row.filename or "").lower()
        fname_matches = sum(1 for t in terms if t in fname_lower)
        if fname_matches:
            score += 0.5 * fname_matches

        # Penalty for very short chunks (likely headers/noise)
        if len(content_lower) < 50:
            score *= 0.5

        scored_results.append((score, row))

    # Sort by score descending
    scored_results.sort(key=lambda x: x[0], reverse=True)

    # Limit results per file (max 4 chunks from any single file)
    MAX_PER_FILE = 4
    file_counts: dict[int, int] = {}
    diverse_results = []
    for score, row in scored_results:
        fid = row.file_id
        file_counts[fid] = file_counts.get(fid, 0) + 1
        if file_counts[fid] <= MAX_PER_FILE:
            diverse_results.append((score, row))
        if len(diverse_results) >= top_k:
            break

    logger.info(
        "Search found %d scored candidates from %d files, returning %d results",
        len(scored_results), len(file_counts), len(diverse_results),
    )

    return [
        {
            "chunk_id": row.id,
            "file_id": row.file_id,
            "content": row.content,
            "page_number": row.page_number,
            "metadata": row.metadata_json,
            "filename": row.filename,
            "file_type": row.file_type,
            "relevance_score": round(score, 3),
        }
        for score, row in diverse_results
    ]


async def store_embedding(
    db: AsyncSession,
    chunk_id: int,
    embedding: list[float],
) -> None:
    """Store embedding (no-op on SQLite without pgvector)."""
    pass


async def bulk_store_embeddings(
    db: AsyncSession,
    chunk_ids: list[int],
    embeddings: list[list[float]],
) -> None:
    """Bulk store embeddings (no-op on SQLite)."""
    pass
