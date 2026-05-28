#!/usr/bin/env python
"""
Bootstrap script — create the first superadmin user.

Usage:
    python create_superadmin.py
    python create_superadmin.py --email admin@company.com --name "Admin User" --password secret123

Run once after initial setup. Subsequent admin users can be created from the
Admin Panel inside the app.
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def main(email: str, full_name: str, password: str) -> None:
    from sqlalchemy import select
    from app.core.database import async_session_factory, engine, Base
    from app.core.security import hash_password
    from app.models import User  # noqa: F401 - registers all models
    from app.models.user import UserRole

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        # Check if email already taken
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            if existing.role == UserRole.SUPERADMIN:
                print(f"[OK] Superadmin already exists: {email}")
                return
            # Upgrade existing user to superadmin
            existing.role = UserRole.SUPERADMIN
            existing.is_active = True
            await db.commit()
            print(f"[UPGRADED] {email} → superadmin")
            return

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.SUPERADMIN,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"[CREATED] Superadmin: {user.full_name} <{user.email}> (id={user.id})")
        print(f"          Role: {user.role}")
        print(f"[DONE] You can now log in at /login and access the Admin Panel.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create the first DataNexus superadmin user")
    parser.add_argument("--email",    default="admin@datanexus.ai", help="Admin email")
    parser.add_argument("--name",     default="Super Admin",         help="Full name")
    parser.add_argument("--password", default="Admin@12345",         help="Password (min 8 chars)")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("[ERROR] Password must be at least 8 characters.")
        sys.exit(1)

    print(f"Creating superadmin: {args.name} <{args.email}>")
    asyncio.run(main(args.email, args.name, args.password))
