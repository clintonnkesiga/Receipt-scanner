from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables if they don't exist.

    Fine for getting started. For evolving the schema over time, add Alembic:
        pip install alembic && alembic init alembic
    and manage migrations instead of relying on create_all.
    """
    # Import models so they're registered on Base.metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    run_migrations()


# Lightweight, idempotent schema patches for columns create_all can't add to
# existing tables. Replace with Alembic once the schema churns more.
_MIGRATIONS = (
    # Per-user categories: add owner_id, drop the old global-unique-by-name
    # constraint/index, and make names unique within an owner instead.
    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS owner_id INTEGER "
    "REFERENCES users(id) ON DELETE SET NULL",
    "ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key",
    "DROP INDEX IF EXISTS ix_categories_name",
    "CREATE INDEX IF NOT EXISTS ix_categories_owner_id ON categories (owner_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_owner_name "
    "ON categories (owner_id, name)",
    # Image rotation (0/90/180/270 degrees clockwise).
    "ALTER TABLE receipts ADD COLUMN IF NOT EXISTS rotation INTEGER NOT NULL DEFAULT 0",
)


def run_migrations() -> None:
    with engine.begin() as conn:
        for stmt in _MIGRATIONS:
            conn.execute(text(stmt))
