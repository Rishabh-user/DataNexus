from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.onedrive.client import OneDriveClient
from app.integrations.onedrive.token_manager import TokenManager
from app.models.file import File
from app.utils.file_utils import (
    compute_file_hash,
    generate_storage_path,
    get_file_type,
    get_mime_type,
    is_allowed_file,
)

logger = get_logger(__name__)


class OneDriveSyncService:
    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id
        self.token_manager = TokenManager(db)

    async def _get_client(self) -> OneDriveClient:
        access_token = await self.token_manager.get_access_token(self.user_id)
        if not access_token:
            refresh_token = await self.token_manager.get_refresh_token(self.user_id)
            if not refresh_token:
                raise ValueError("No OneDrive tokens found. Please reconnect.")

            from app.integrations.onedrive.auth import refresh_access_token

            tokens = refresh_access_token(refresh_token)
            await self.token_manager.store_tokens(
                user_id=self.user_id,
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                expires_at=tokens["expires_at"],
            )
            access_token = tokens["access_token"]

        return OneDriveClient(access_token)

    async def sync_folder(self, folder_id: str | None = None) -> dict:
        token_record = await self.token_manager.get_token_record(self.user_id)
        if not token_record:
            raise ValueError("OneDrive not connected")

        effective_folder_id = folder_id or token_record.selected_folder_id
        if not effective_folder_id:
            raise ValueError("No folder selected for sync")

        client = await self._get_client()
        delta_link = token_record.delta_link

        synced = 0
        skipped = 0
        failed = 0
        all_items = []

        # Use delta API for incremental sync
        try:
            delta_result = await client.get_delta(effective_folder_id, delta_link)
            all_items.extend(delta_result["items"])

            while delta_result.get("next_link"):
                delta_result = await client.get_delta(
                    effective_folder_id, delta_result["next_link"]
                )
                all_items.extend(delta_result["items"])

            if delta_result.get("delta_link"):
                await self.token_manager.update_delta_link(
                    self.user_id, delta_result["delta_link"]
                )
        except Exception as e:
            logger.warning("Delta sync failed, falling back to full listing: %s", str(e))
            all_items = []

        # If delta returned nothing (or failed), do a full folder listing
        # This ensures all files in the folder are synced
        if not all_items:
            try:
                listed = await client.list_files(effective_folder_id)
                for f in listed:
                    if not f["is_folder"]:
                        # Convert list_files format to delta-like format
                        all_items.append({
                            "id": f["item_id"],
                            "name": f["name"],
                            "size": f.get("size", 0),
                        })
            except Exception as e:
                logger.error("Full folder listing also failed: %s", str(e))
                raise ValueError(f"Could not list files in folder: {str(e)}")

        for item in all_items:
            if "folder" in item or "deleted" in item:
                continue

            filename = item.get("name", "")
            if not is_allowed_file(filename):
                continue

            try:
                # Skip if already synced by OneDrive item ID
                existing = await self.db.execute(
                    select(File).where(
                        File.user_id == self.user_id,
                        File.onedrive_item_id == item["id"],
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                storage_path = generate_storage_path(self.user_id, filename)
                await client.download_file(item["id"], storage_path)

                file_hash = compute_file_hash(storage_path)

                # Skip if duplicate content (different OneDrive item but same file)
                dup = await self.db.execute(
                    select(File).where(
                        File.user_id == self.user_id,
                        File.file_hash == file_hash,
                    )
                )
                existing_dup = dup.scalar_one_or_none()
                if existing_dup:
                    # Check if the existing file is still on disk
                    if Path(existing_dup.storage_path).exists():
                        storage_path.unlink(missing_ok=True)
                        logger.info("Skipping duplicate file: %s", filename)
                        skipped += 1
                        continue
                    else:
                        # Orphaned record — clean it up
                        logger.info("Cleaning up orphaned record for: %s", existing_dup.filename)
                        await self.db.delete(existing_dup)
                        await self.db.flush()

                file_record = File(
                    user_id=self.user_id,
                    filename=filename,
                    file_type=get_file_type(filename),
                    mime_type=get_mime_type(filename),
                    source="onedrive",
                    onedrive_item_id=item["id"],
                    storage_path=str(storage_path),
                    file_size=item.get("size", 0),
                    file_hash=file_hash,
                    processing_status="pending",
                )
                self.db.add(file_record)
                await self.db.flush()
                synced += 1

            except Exception as e:
                logger.error("Failed to sync file %s: %s", filename, str(e))
                failed += 1

        logger.info("Sync complete: %d synced, %d skipped, %d failed", synced, skipped, failed)
        return {"files_synced": synced, "files_skipped": skipped, "files_failed": failed}
