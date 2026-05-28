from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.files import router as files_router
from app.api.v1.onedrive import router as onedrive_router
from app.api.v1.reports import router as reports_router
from app.api.v1.search import router as search_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(files_router)
api_router.include_router(onedrive_router)
api_router.include_router(chat_router)
api_router.include_router(search_router)
api_router.include_router(reports_router)
