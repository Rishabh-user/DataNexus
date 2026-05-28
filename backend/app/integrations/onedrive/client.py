from pathlib import Path

import httpx

from app.core.logging import get_logger
from app.utils.retry import async_retry

logger = get_logger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class OneDriveClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {"Authorization": f"Bearer {access_token}"}

    @async_retry(max_retries=3, delay=1.0, exceptions=(httpx.HTTPStatusError,))
    async def list_files(self, folder_id: str | None = None) -> list[dict]:
        async with httpx.AsyncClient() as client:
            if folder_id:
                url = f"{GRAPH_BASE_URL}/me/drive/items/{folder_id}/children"
            else:
                url = f"{GRAPH_BASE_URL}/me/drive/root/children"

            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()

            items = []
            for item in data.get("value", []):
                items.append({
                    "item_id": item["id"],
                    "name": item["name"],
                    "size": item.get("size", 0),
                    "mime_type": item.get("file", {}).get("mimeType"),
                    "last_modified": item.get("lastModifiedDateTime"),
                    "is_folder": "folder" in item,
                })
            return items

    @async_retry(max_retries=3, delay=2.0, exceptions=(httpx.HTTPStatusError,))
    async def download_file(self, item_id: str, destination: Path) -> Path:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            url = f"{GRAPH_BASE_URL}/me/drive/items/{item_id}/content"
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()

            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, "wb") as f:
                f.write(response.content)

            logger.info("Downloaded file %s to %s", item_id, destination)
            return destination

    @async_retry(max_retries=3, delay=1.0, exceptions=(httpx.HTTPStatusError,))
    async def get_file_metadata(self, item_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            url = f"{GRAPH_BASE_URL}/me/drive/items/{item_id}"
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    @async_retry(max_retries=3, delay=1.0, exceptions=(httpx.HTTPStatusError,))
    async def get_delta(self, folder_id: str, delta_link: str | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            if delta_link:
                url = delta_link
            else:
                url = f"{GRAPH_BASE_URL}/me/drive/items/{folder_id}/delta"

            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()

            return {
                "items": data.get("value", []),
                "delta_link": data.get("@odata.deltaLink"),
                "next_link": data.get("@odata.nextLink"),
            }
