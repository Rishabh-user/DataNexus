from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import build_chat_context
from app.ai.llm import chat_completion
from app.ai.retriever import retrieve_context
from app.core.logging import get_logger

logger = get_logger(__name__)


async def rag_query(
    db: AsyncSession,
    query: str,
    user_id: int,
    chat_history: list[dict] | None = None,
    file_type_filter: str | None = None,
) -> dict:
    # 1. Retrieve relevant context
    retrieval = await retrieve_context(
        db=db,
        query=query,
        user_id=user_id,
        file_type_filter=file_type_filter,
    )

    # 2. Build prompt with context
    system_prompt, user_prompt = build_chat_context(
        context=retrieval["context"],
        structured_data=retrieval["structured_data"],
        chat_history=chat_history or [],
        question=query,
    )

    # 3. Build messages using Claude's native multi-turn format
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history as proper Claude message turns
    history = chat_history or []
    recent_history = history[-10:]  # Last 10 messages
    for msg in recent_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Add the current user question with retrieved context
    messages.append({"role": "user", "content": user_prompt})

    answer = await chat_completion(messages, max_tokens=4096)

    return {
        "answer": answer,
        "sources": retrieval["sources"],
    }
