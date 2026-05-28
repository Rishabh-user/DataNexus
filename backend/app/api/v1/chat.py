from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import PaginationParams
from app.core.logging import get_logger
from app.core.security import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatQueryRequest,
    ChatResponse,
    ChatSessionResponse,
)
from app.services.chat_service import get_chat_history, get_chat_sessions, process_chat_query

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat_query(
    request: ChatQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN, UserRole.SUPERADMIN)),
):
    try:
        return await process_chat_query(db, current_user.id, request)
    except Exception as e:
        error_msg = str(e)
        logger.error("Chat query failed: %s", error_msg)

        # Provide friendly error messages for common API errors
        if "overloaded" in error_msg.lower() or "529" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="Claude AI is temporarily overloaded. Please wait a moment and try again.",
            )
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a moment and try again.",
            )
        if "authentication" in error_msg.lower() or "401" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="Claude API key is invalid or not configured. Check CLAUDE_API_KEY in .env file.",
            )
        raise HTTPException(
            status_code=500,
            detail=f"AI service error: {error_msg[:200]}",
        )


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = await get_chat_sessions(db, current_user.id, pagination.skip, pagination.limit)
    return [ChatSessionResponse.model_validate(s) for s in sessions]


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_history(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session, messages = await get_chat_history(db, current_user.id, session_id)
    return ChatHistoryResponse(
        session=ChatSessionResponse.model_validate(session),
        messages=[ChatMessageResponse.model_validate(m) for m in messages],
    )
