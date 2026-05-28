from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.search import SearchResult, SemanticSearchRequest, StructuredSearchRequest
from app.services.search_service import semantic_search, structured_search

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("/semantic", response_model=list[SearchResult])
async def search_semantic(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await semantic_search(
        db=db,
        user_id=current_user.id,
        query=request.query,
        top_k=request.top_k,
        file_type_filter=request.file_type_filter,
    )


@router.post("/structured", response_model=list[SearchResult])
async def search_structured(
    request: StructuredSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await structured_search(
        db=db,
        user_id=current_user.id,
        query=request.query,
        data_type=request.data_type,
    )
