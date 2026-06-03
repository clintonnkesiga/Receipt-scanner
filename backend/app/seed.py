"""Seed the database with a super-admin user.

Run from the backend/ directory with the venv active:

    python -m app.seed            # idempotent: skip if the super-admin exists
    python -m app.seed --recreate # drop the existing super-admin and recreate

Credentials come from .env (SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD /
SUPERADMIN_NAME). Use --recreate (or -f/--force) to pick up changed
credentials in .env.
"""
import argparse

from sqlalchemy import select

from .config import settings
from .database import SessionLocal, init_db
from .security import hash_password
from . import models


def seed_superadmin(recreate: bool = False) -> None:
    init_db()  # ensure tables exist
    db = SessionLocal()
    try:
        existing = db.scalar(
            select(models.User).where(models.User.email == settings.superadmin_email)
        )
        if existing:
            if not recreate:
                print(f"✓ Super-admin already exists: {existing.email} (role={existing.role})")
                print("  Pass --recreate to drop and recreate it with the current .env credentials.")
                return
            db.delete(existing)
            db.commit()
            print(f"✗ Dropped existing super-admin: {existing.email}")

        user = models.User(
            email=settings.superadmin_email,
            full_name=settings.superadmin_name,
            hashed_password=hash_password(settings.superadmin_password),
            role="superadmin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"✓ Created super-admin: {user.email}")
        print("  Log in with the SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD from your .env.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the super-admin user.")
    parser.add_argument(
        "-f", "--force", "--recreate",
        dest="recreate",
        action="store_true",
        help="Drop the existing super-admin and recreate it with current .env credentials.",
    )
    args = parser.parse_args()
    seed_superadmin(recreate=args.recreate)
