import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_list_files_empty(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/files", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_upload_unsupported_file(client: AsyncClient, auth_headers):
    response = await client.post(
        "/api/v1/files/upload",
        headers=auth_headers,
        files={"file": ("test.exe", b"fake content", "application/octet-stream")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_file_not_found(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/files/9999", headers=auth_headers)
    assert response.status_code == 404
