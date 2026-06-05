from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str | None = None
    role: str
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    password: str = Field(min_length=8)
    role: str = "user"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=8)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class LineItemBase(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class LineItemOut(LineItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ReceiptBase(BaseModel):
    merchant: str | None = None
    purchase_date: date | None = None
    total: Decimal | None = None
    currency: str | None = None
    category: str | None = None


class ReceiptCreate(ReceiptBase):
    """Payload to save/correct a receipt after OCR review."""
    image_path: str | None = None
    raw_ocr_text: str | None = None
    line_items: list[LineItemBase] = []


class ReceiptUpdate(BaseModel):
    """Partial update for an existing receipt (PATCH — all fields optional)."""
    merchant: str | None = None
    purchase_date: date | None = None
    total: Decimal | None = None
    currency: str | None = None
    category: str | None = None


class ReceiptOut(ReceiptBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int | None = None
    owner_email: str | None = None
    image_path: str | None = None
    raw_ocr_text: str | None = None
    created_at: datetime
    line_items: list[LineItemOut] = []


class ScanResult(BaseModel):
    """Returned right after upload+OCR, before the user confirms/saves."""
    image_path: str
    raw_ocr_text: str
    parsed: ReceiptCreate


# --- Dashboard stats ---
class CategoryStat(BaseModel):
    category: str | None = None
    total: Decimal
    count: int


class MonthStat(BaseModel):
    month: str  # "YYYY-MM"
    total: Decimal
    count: int


class CurrencyStat(BaseModel):
    currency: str | None = None
    total: Decimal
    count: int


class MerchantStat(BaseModel):
    merchant: str | None = None
    total: Decimal
    count: int


class LargestReceipt(BaseModel):
    id: int
    merchant: str | None = None
    total: Decimal
    currency: str | None = None
    purchase_date: date | None = None


class MonthTrend(BaseModel):
    """This month's spend vs last month (calendar months)."""
    current: Decimal
    previous: Decimal
    change_pct: float | None = None  # None when previous is 0 (no baseline)


class ReceiptStats(BaseModel):
    total_spend: Decimal
    receipt_count: int
    recent_count: int = 0  # receipts added in the last 30 days
    last_receipt_date: date | None = None
    by_category: list[CategoryStat] = []
    by_month: list[MonthStat] = []
    by_currency: list[CurrencyStat] = []
    top_merchants: list[MerchantStat] = []
    largest_receipt: LargestReceipt | None = None
    month_trend: MonthTrend | None = None
