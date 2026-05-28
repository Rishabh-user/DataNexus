from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.integrations.onedrive.auth import exchange_code_for_tokens, get_auth_url
from app.integrations.onedrive.client import OneDriveClient
from app.integrations.onedrive.token_manager import TokenManager
from app.integrations.onedrive.sync import OneDriveSyncService
from app.models.file import File
from app.models.user import User, UserRole
from app.schemas.onedrive import (
    OneDriveAuthURL,
    OneDriveConnectionStatus,
    OneDriveFileItem,
    OneDriveFileList,
    SyncRequest,
    SyncStatusResponse,
)

router = APIRouter(prefix="/onedrive", tags=["OneDrive"])


@router.get("/auth-url", response_model=OneDriveAuthURL)
async def get_onedrive_auth_url(current_user: User = Depends(get_current_user)):
    auth_url = get_auth_url(state=str(current_user.id))
    return OneDriveAuthURL(auth_url=auth_url)


@router.get("/callback")
async def onedrive_callback(
    code: str,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    try:
        user_id = int(state)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    tokens = exchange_code_for_tokens(code)

    token_manager = TokenManager(db)
    await token_manager.store_tokens(
        user_id=user_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"],
        scopes=tokens.get("scopes"),
    )
    await db.commit()

    # Return a simple HTML page that closes the popup / redirects
    return {"status": "connected", "message": "OneDrive connected successfully. You can close this tab."}


@router.get("/status", response_model=OneDriveConnectionStatus)
async def connection_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token_manager = TokenManager(db)
    token_record = await token_manager.get_token_record(current_user.id)

    return OneDriveConnectionStatus(
        connected=token_record is not None,
        selected_folder=token_record.selected_folder_name if token_record else None,
    )


@router.get("/browse", response_model=OneDriveFileList)
async def browse_onedrive(
    folder_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Browse OneDrive folders and files. Pass folder_id to drill into a folder."""
    token_manager = TokenManager(db)
    access_token = await token_manager.get_access_token(current_user.id)

    if not access_token:
        # Try refreshing
        refresh_token = await token_manager.get_refresh_token(current_user.id)
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OneDrive not connected. Please connect first.",
            )
        from app.integrations.onedrive.auth import refresh_access_token
        tokens = refresh_access_token(refresh_token)
        await token_manager.store_tokens(
            user_id=current_user.id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_at=tokens["expires_at"],
        )
        await db.commit()
        access_token = tokens["access_token"]

    client = OneDriveClient(access_token)
    files = await client.list_files(folder_id)

    return OneDriveFileList(
        files=[OneDriveFileItem(**f) for f in files],
        folder_name=folder_id,
    )


# Keep old endpoint for backwards compat
@router.get("/files", response_model=OneDriveFileList)
async def list_onedrive_files(
    folder_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await browse_onedrive(folder_id, db, current_user)


@router.post("/select-folder")
async def select_folder(
    folder_id: str,
    folder_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN, UserRole.SUPERADMIN)),
):
    token_manager = TokenManager(db)
    await token_manager.set_selected_folder(current_user.id, folder_id, folder_name)
    await db.commit()
    return {"status": "ok", "message": f"Folder '{folder_name}' selected for sync"}


@router.post("/sync", response_model=SyncStatusResponse)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    request: SyncRequest = SyncRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN, UserRole.SUPERADMIN)),
):
    """Run sync directly, then auto-process synced files."""
    from app.api.v1.files import _process_files_sequential

    try:
        sync_service = OneDriveSyncService(db, current_user.id)
        result = await sync_service.sync_folder(request.folder_id)
        await db.commit()

        # Auto-process newly synced files (sequentially to avoid SQLite locking)
        pending_result = await db.execute(
            select(File).where(
                File.user_id == current_user.id,
                File.source == "onedrive",
                File.processing_status == "pending",
            )
        )
        pending_files = pending_result.scalars().all()
        if pending_files:
            file_ids = [f.id for f in pending_files]
            background_tasks.add_task(_process_files_sequential, file_ids)

        skipped = result.get("files_skipped", 0)
        return SyncStatusResponse(
            task_id="direct-sync",
            status="completed",
            files_synced=result["files_synced"],
            files_failed=result["files_failed"],
            message=f"Synced {result['files_synced']} new files{f', {skipped} already synced' if skipped else ''}, processing {len(pending_files)} in background",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
