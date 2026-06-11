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
    # Tax/VAT and net amount capture.
    "ALTER TABLE receipts ADD COLUMN IF NOT EXISTS tax_amount NUMERIC(14,2)",
    "ALTER TABLE receipts ADD COLUMN IF NOT EXISTS net_amount NUMERIC(14,2)",
    # FX rate: multiply total by this to convert to the user's base currency.
    "ALTER TABLE receipts ADD COLUMN IF NOT EXISTS fx_rate NUMERIC(18,6)",
    # Unique transaction id for duplicate detection.
    "ALTER TABLE receipts ADD COLUMN IF NOT EXISTS fiscal_id VARCHAR(64)",
    "CREATE INDEX IF NOT EXISTS ix_receipts_fiscal_id ON receipts (fiscal_id)",
    # Budgets table (monthly limit per category).
    """CREATE TABLE IF NOT EXISTS budgets (
        id          SERIAL PRIMARY KEY,
        owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        category    VARCHAR(32),
        monthly_limit NUMERIC(14,2) NOT NULL,
        currency    VARCHAR(8),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_budgets_owner_category UNIQUE (owner_id, category)
    )""",
    "CREATE INDEX IF NOT EXISTS ix_budgets_owner_id ON budgets (owner_id)",
    # Account & security columns on users
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(128)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR(128)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_expires TIMESTAMPTZ",
    # Audit log
    """CREATE TABLE IF NOT EXISTS audit_logs (
        id           SERIAL PRIMARY KEY,
        user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
        user_email   VARCHAR(255),
        action       VARCHAR(64) NOT NULL,
        target_type  VARCHAR(32),
        target_id    INTEGER,
        detail       TEXT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at DESC)",
    # Soft-delete / trash: NULL = active, timestamp = in the Trash.
    "ALTER TABLE receipts ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS ix_receipts_deleted_at ON receipts (deleted_at)",
)


def run_migrations() -> None:
    with engine.begin() as conn:
        for stmt in _MIGRATIONS:
            conn.execute(text(stmt))
