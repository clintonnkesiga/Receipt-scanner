"""Seed the database with a super-admin user.

Run from the backend/ directory with the venv active:

    python -m app.seed

Credentials come from .env (SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD /
SUPERADMIN_NAME). Idempotent: re-running won't create duplicates.
"""
from sqlalchemy import select

from .config import settings
from .database import SessionLocal, init_db
from .security import hash_password
from . import models


def seed_superadmin() -> None:
    init_db()  # ensure tables exist
    db = SessionLocal()
    try:
        existing = db.scalar(
            select(models.User).where(models.User.email == settings.superadmin_email)
        )
        if existing:
            print(f"✓ Super-admin already exists: {existing.email} (role={existing.role})")
            return

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
    seed_superadmin()
