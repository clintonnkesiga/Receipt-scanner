from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    String, Text, ForeignKey, Numeric, Date, DateTime, Boolean, Integer, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="user")  # superadmin | admin | user
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    # TOTP 2FA
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Password reset (token stored as SHA-256 hex digest)
    reset_token: Mapped[str | None] = mapped_column(String(128))
    reset_token_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Email verification
    verification_token: Mapped[str | None] = mapped_column(String(128))
    verification_token_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    """A receipt category (e.g. grocery, fuel, restaurant).

    Receipts store the category *name* as a plain string (Receipt.category),
    so this table is the editable list the UI offers — renaming one cascades
    to the receipts that use it (handled in the router).

    `owner_id` scopes categories per-user: NULL = a shared/system default
    (seeded, visible to everyone, admin-managed); a user id = that user's own
    category, visible and editable only by them. Names are unique within an
    owner's scope, not globally.
    """
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_categories_owner_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The user who created the receipt. Kept (set NULL) if that user is deleted.
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    merchant: Mapped[str | None] = mapped_column(String(255))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    category: Mapped[str | None] = mapped_column(String(32))  # grocery | fuel | other
    image_path: Mapped[str | None] = mapped_column(String(512))
    raw_ocr_text: Mapped[str | None] = mapped_column(Text)
    # Unique transaction id printed on the receipt (fiscal/cash-sale/invoice no),
    # used for reliable duplicate detection. NULL when none could be parsed.
    fiscal_id: Mapped[str | None] = mapped_column(String(64), index=True)
    rotation: Mapped[int] = mapped_column(Integer, default=0)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    # Exchange rate: multiply total by this to convert to the user's base currency.
    # NULL means no conversion has been set.
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    # Soft-delete: NULL = active; a timestamp = in the Trash (recoverable).
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User | None"] = relationship()

    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
    )

    @property
    def owner_email(self) -> str | None:
        return self.owner.email if self.owner else None


class Budget(Base):
    """Monthly spending limit per category (or across all categories if NULL)."""
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("owner_id", "category", name="uq_budgets_owner_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str | None] = mapped_column(String(32))  # NULL = all-category budget
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship()


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"))
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    receipt: Mapped["Receipt"] = relationship(back_populates="line_items")


class AuditLog(Base):
    """Append-only record of security-relevant actions."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    user_email: Mapped[str | None] = mapped_column(String(255))  # snapshot (user may be deleted)
    action: Mapped[str] = mapped_column(String(64))              # e.g. "receipt.delete"
    target_type: Mapped[str | None] = mapped_column(String(32))  # "receipt" | "budget" | "user"
    target_id: Mapped[int | None]
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
