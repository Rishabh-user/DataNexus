from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.onedrive_token import OneDriveToken
from app.utils.encryption import decrypt_value, encrypt_value

logger = get_logger(__name__)


class TokenManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store_tokens(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        scopes: str | None = None,
    ) -> OneDriveToken:
        result = await self.db.execute(
            select(OneDriveToken).where(OneDriveToken.user_id == user_id)
        )
        token_record = result.scalar_one_or_none()

        encrypted_access = encrypt_value(access_token)
        encrypted_refresh = encrypt_value(refresh_token)

        if token_record:
            token_record.access_token_encrypted = encrypted_access
            token_record.refresh_token_encrypted = encrypted_refresh
            token_record.expires_at = expires_at
            if scopes:
                token_record.scopes = scopes
        else:
            token_record = OneDriveToken(
                user_id=user_id,
                access_token_encrypted=encrypted_access,
                refresh_token_encrypted=encrypted_refresh,
                expires_at=expires_at,
                scopes=scopes,
            )
            self.db.add(token_record)

        await self.db.flush()
        return token_record

    async def get_access_token(self, user_id: int) -> str | None:
        result = await self.db.execute(
            select(OneDriveToken).where(OneDriveToken.user_id == user_id)
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            return None

        # Handle both naive and aware datetimes (SQLite stores naive)
        exp = token_record.expires_at
        now = datetime.now(timezone.utc)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            logger.info("Token expired for user %d, refreshing...", user_id)
            return None

        return decrypt_value(token_record.access_token_encrypted)

    async def get_refresh_token(self, user_id: int) -> str | None:
        result = await self.db.execute(
            select(OneDriveToken).where(OneDriveToken.user_id == user_id)
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            return None
        return decrypt_value(token_record.refresh_token_encrypted)

    async def get_token_record(self, user_id: int) -> OneDriveToken | None:
        result = await self.db.execute(
            select(OneDriveToken).where(OneDriveToken.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def set_selected_folder(
        self, user_id: int, folder_id: str, folder_name: str
    ) -> None:
        result = await self.db.execute(
            select(OneDriveToken).where(OneDriveToken.user_id == user_id)
        )
        token_record = result.scalar_one_or_none()
        if token_record:
            token_record.selected_folder_id = folder_id
            token_record.selected_folder_name = folder_name
            await self.db.flush()

    async def update_delta_link(self, user_id: int, delta_link: str) -> None:
        result = await self.db.execute(
            select(OneDriveToken).where(OneDriveToken.user_id == user_id)
        )
        token_record = result.scalar_one_or_none()
        if token_record:
            token_record.delta_link = delta_link
            await self.db.flush()
