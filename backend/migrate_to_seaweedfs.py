#!/usr/bin/env python3
"""One-time migration: move existing local receipt images into SeaweedFS.

Run once after SeaweedFS is up and before deploying the new backend code:

    cd backend
    python migrate_to_seaweedfs.py

The script skips receipts whose image_path already starts with '/receipts/'
(already migrated) and skips any whose file is missing on disk.
"""
import asyncio
import os
import sys
import uuid

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(__file__))

from app.config import settings
from app import models


async def main() -> None:
    filer_url = settings.seaweedfs_filer_url
    engine = create_engine(settings.database_url)

    with Session(engine) as session:
        receipts = (
            session.query(models.Receipt)
            .filter(models.Receipt.image_path.isnot(None))
            .all()
        )

    print(f"Found {len(receipts)} receipt(s) with an image_path.")
    migrated = skipped = missing = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for receipt in receipts:
            local_path = receipt.image_path

            if local_path.startswith("/receipts/"):
                print(f"  [skip] receipt {receipt.id}: already migrated → {local_path}")
                skipped += 1
                continue

            if not os.path.isfile(local_path):
                print(f"  [miss] receipt {receipt.id}: file not found at {local_path}")
                missing += 1
                continue

            with open(local_path, "rb") as fh:
                data = fh.read()

            ext = os.path.splitext(local_path)[1] or ".jpg"
            name = f"{uuid.uuid4().hex}{ext}"
            user_id = receipt.owner_id or 0
            filer_path = f"/receipts/{user_id}/{name}"

            resp = await client.post(f"{filer_url}{filer_path}", content=data)
            resp.raise_for_status()

            with Session(engine) as session:
                r = session.get(models.Receipt, receipt.id)
                r.image_path = filer_path
                session.commit()

            print(f"  [ok]   receipt {receipt.id}: {local_path} → {filer_path}")
            migrated += 1

    print(f"\nDone: {migrated} migrated, {skipped} already done, {missing} files missing.")


if __name__ == "__main__":
    asyncio.run(main())
