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


# Starter categories. The parser auto-assigns the first three, so seeding them
# keeps auto-categorised receipts aligned with the managed picker. Admins add
# the rest (and their own) from the Categories page.
DEFAULT_CATEGORIES = ["grocery", "fuel", "other", "restaurant", "pharmacy", "transport"]


def seed_default_categories() -> None:
    """Insert any missing starter categories. Idempotent — safe on every boot."""
    db = SessionLocal()
    try:
        existing = set(db.scalars(select(models.Category.name)).all())
        added = 0
        for name in DEFAULT_CATEGORIES:
            if name not in existing:
                db.add(models.Category(name=name))
                added += 1
        if added:
            db.commit()
    finally:
        db.close()


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
