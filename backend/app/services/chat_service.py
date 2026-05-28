from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chains import rag_query
from app.ai.llm import generate_chat_response
from app.ai.prompts import TITLE_GENERATION_PROMPT
from app.core.logging import get_logger
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import ChatQueryRequest, ChatResponse, SourceReference

logger = get_logger(__name__)


async def process_chat_query(
    db: AsyncSession,
    user_id: int,
    request: ChatQueryRequest,
) -> ChatResponse:
    # 1. Get or create session
    if request.session_id:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == request.session_id,
                ChatSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            session = await _create_session(db, user_id, request.query)
    else:
        session = await _create_session(db, user_id, request.query)

    # 2. Store user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.query,
    )
    db.add(user_msg)
    await db.flush()

    # 3. Get conversation history
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    history_messages = result.scalars().all()
    chat_history = [
        {"role": msg.role, "content": msg.content}
        for msg in history_messages[:-1]  # Exclude current message
    ]

    # 4. Run RAG query
    rag_result = await rag_query(
        db=db,
        query=request.query,
        user_id=user_id,
        chat_history=chat_history,
    )

    # 5. Build source references
    sources = [
        SourceReference(
            file_id=s["file_id"],
            filename=s["filename"],
            chunk_content=s["content"][:200],
            page_number=s.get("page_number"),
            relevance_score=s["relevance_score"],
        )
        for s in rag_result["sources"]
    ]

    # 6. Store assistant message
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=rag_result["answer"],
        sources_json={
            "sources": [s.model_dump() for s in sources]
        },
    )
    db.add(assistant_msg)
    await db.flush()

    return ChatResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        answer=rag_result["answer"],
        sources=sources,
    )


async def get_chat_sessions(
    db: AsyncSession, user_id: int, skip: int = 0, limit: int = 20
) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_chat_history(
    db: AsyncSession, user_id: int, session_id: int
) -> tuple[ChatSession, list[ChatMessage]]:
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = list(result.scalars().all())
    return session, messages


async def _create_session(db: AsyncSession, user_id: int, first_message: str) -> ChatSession:
    # Generate a title from the first message
    try:
        title = await generate_chat_response(
            system_prompt="You are a title generator. Return only a short title.",
            user_prompt=TITLE_GENERATION_PROMPT.format(message=first_message),
        )
        title = title.strip().strip('"')[:100]
    except Exception:
        title = first_message[:50]

    session = ChatSession(user_id=user_id, title=title)
    db.add(session)
    await db.flush()
    return session
