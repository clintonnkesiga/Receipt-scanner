"""SeaweedFS filer client — upload, stream, and delete receipt files."""
import os
import uuid

import httpx

from .config import settings


async def upload(data: bytes, original_filename: str, user_id: int) -> str:
    """Upload bytes to SeaweedFS; return the filer path saved in the DB."""
    ext = os.path.splitext(original_filename)[1] or ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    path = f"/receipts/{user_id}/{name}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.seaweedfs_filer_url}{path}",
            files={"file": (name, data)},
            timeout=30.0,
        )
        resp.raise_for_status()
    return path


async def stream(filer_path: str) -> tuple[bytes, str]:
    """Fetch file bytes and content-type from the filer."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.seaweedfs_filer_url}{filer_path}",
            timeout=30.0,
        )
        resp.raise_for_status()
    return resp.content, resp.headers.get("content-type", "application/octet-stream")


async def delete(filer_path: str) -> None:
    """Delete a file from the filer; silently ignores 404."""
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{settings.seaweedfs_filer_url}{filer_path}",
            timeout=10.0,
        )
        if resp.status_code not in (200, 204, 404):
            resp.raise_for_status()
