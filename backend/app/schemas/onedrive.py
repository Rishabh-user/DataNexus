from datetime import datetime

from pydantic import BaseModel


class OneDriveAuthURL(BaseModel):
    auth_url: str


class OneDriveCallbackRequest(BaseModel):
    code: str
    state: str | None = None


class OneDriveFileItem(BaseModel):
    item_id: str
    name: str
    size: int
    mime_type: str | None = None
    last_modified: datetime | None = None
    is_folder: bool = False


class OneDriveFileList(BaseModel):
    files: list[OneDriveFileItem]
    folder_name: str | None = None


class SyncRequest(BaseModel):
    folder_id: str | None = None


class SyncStatusResponse(BaseModel):
    task_id: str
    status: str
    files_synced: int = 0
    files_failed: int = 0
    message: str | None = None


class OneDriveConnectionStatus(BaseModel):
    connected: bool
    selected_folder: str | None = None
    last_sync: datetime | None = None
