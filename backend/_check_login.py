import asyncio
import asyncpg
import sys
sys.path.insert(0, '.')
from app.core.security import verify_password

PG_URL = (
    "postgresql://datanexus_69x2_user:fsRkbouPhQhJH4nVgOUVaCx2sBeOU37H"
    "@dpg-d8c1ds6q1p3s73fst290-a.oregon-postgres.render.com/datanexus_69x2"
)

async def check():
    conn = await asyncpg.connect(PG_URL, ssl="require")
    row = await conn.fetchrow(
        "SELECT email, hashed_password, is_active FROM users WHERE email = $1",
        "admin@datanexus.ai"
    )
    await conn.close()
    if row:
        print("Found:", row["email"], "| active:", row["is_active"])
        ok = verify_password("Admin@12345", row["hashed_password"])
        print("Password 'Admin@12345' verify:", ok)
    else:
        print("User NOT found in database")

asyncio.run(check())
