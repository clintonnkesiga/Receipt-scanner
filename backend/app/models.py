from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Text, ForeignKey, Numeric, Date, DateTime, Boolean, func
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
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    category: Mapped[str | None] = mapped_column(String(32))  # grocery | fuel | other
    image_path: Mapped[str | None] = mapped_column(String(512))
    raw_ocr_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
    )


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"))
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    receipt: Mapped["Receipt"] = relationship(back_populates="line_items")
