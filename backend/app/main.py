from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging

_APP_DIR = Path(__file__).resolve().parent
from app.models import (  # noqa: F401 - imported so Base.metadata knows all tables
    ChatMessage,
    ChatSession,
    DocumentChunk,
    ExtractedData,
    File,
    OneDriveToken,
    Report,
    TaskLog,
    Team,
    TeamMember,
    User,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Starting %s...", settings.app_name)

    # Auto-create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified.")

    yield
    logger.info("Shutting down %s...", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="AI-powered Data Extraction and Intelligence Platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    register_exception_handlers(app)

    # Show full tracebacks in dev mode
    if settings.debug:
        from fastapi import Request
        from fastapi.responses import JSONResponse
        import traceback

        @app.exception_handler(Exception)
        async def debug_exception_handler(request: Request, exc: Exception):
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc), "traceback": traceback.format_exc()},
            )

    # Routes
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Static files
    app.mount("/static", StaticFiles(directory=str(_APP_DIR / "static")), name="static")

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "app": settings.app_name}

    # HTML pages — proper URL routes (not hash-based)
    @app.get("/login", response_class=HTMLResponse)
    async def login_page():
        return (_APP_DIR / "templates" / "login.html").read_text(encoding="utf-8")

    # All app pages serve the same SPA shell — JS handles routing
    _index_html = None

    def _get_index():
        nonlocal _index_html
        if _index_html is None or settings.debug:
            _index_html = (_APP_DIR / "templates" / "index.html").read_text(encoding="utf-8")
        return _index_html

    @app.get("/", response_class=HTMLResponse)
    async def index_page():
        return _get_index()

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_page():
        return _get_index()

    @app.get("/files", response_class=HTMLResponse)
    async def files_page():
        return _get_index()

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page():
        return _get_index()

    @app.get("/ppt", response_class=HTMLResponse)
    async def ppt_page():
        return _get_index()

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page():
        return _get_index()

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page():
        return _get_index()

    @app.get("/teams", response_class=HTMLResponse)
    async def teams_page():
        return _get_index()

    return app


app = create_app()
