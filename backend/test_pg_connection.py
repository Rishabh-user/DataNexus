"""Test Render PostgreSQL connection and create all tables."""
import asyncio
import asyncpg

from app.core.config import settings

# Read connection URL from .env via settings
# asyncpg needs plain postgresql:// not postgresql+asyncpg://
PG_URL = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


async def test_connection():
    print("Step 1: Connecting to Render PostgreSQL...")
    print(f"  URL: {PG_URL[:60]}...")
    conn = await asyncpg.connect(PG_URL, ssl="require")
    version = await conn.fetchval("SELECT version()")
    tables  = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    )
    await conn.close()
    print(f"  Connected! PostgreSQL: {version[:60]}")
    existing = [r["tablename"] for r in tables]
    print(f"  Existing tables: {existing or ['none yet']}")
    return existing


async def create_tables():
    print("\nStep 2: Creating all application tables...")
    from app.core.database import Base, engine
    from app.models import (  # noqa: F401 — registers all models with Base
        ChatMessage, ChatSession, DocumentChunk, ExtractedData,
        File, OneDriveToken, Report, TaskLog, User,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  All tables created successfully!")


async def verify_tables():
    print("\nStep 3: Verifying tables in database...")
    conn = await asyncpg.connect(PG_URL, ssl="require")
    tables = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )
    await conn.close()
    names = [r["tablename"] for r in tables]
    print(f"  Tables found ({len(names)}):")
    for t in names:
        print(f"    - {t}")


async def main():
    await test_connection()
    await create_tables()
    await verify_tables()
    print("\nDone! PostgreSQL is ready to use.")


asyncio.run(main())
