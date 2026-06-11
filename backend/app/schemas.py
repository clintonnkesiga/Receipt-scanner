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
    is_verified: bool = False
    totp_enabled: bool = False
    avatar_url: str | None = None


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


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class TwoFASetupOut(BaseModel):
    secret: str
    qr_data_uri: str
    provisioning_uri: str


class TwoFACode(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_email: str | None = None
    action: str
    target_type: str | None = None
    target_id: int | None = None
    detail: str | None = None
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditLogOut]
    total: int


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    owner_id: int | None = None


# --- Budgets ---
class BudgetCreate(BaseModel):
    category: str | None = None  # None = all-category budget
    monthly_limit: Decimal = Field(gt=0)
    currency: str | None = None


class BudgetUpdate(BaseModel):
    monthly_limit: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str | None = None
    monthly_limit: Decimal
    currency: str | None = None


class BudgetUsage(BaseModel):
    """A budget with the current-month spend wired in."""
    budget: BudgetOut
    spent: Decimal
    pct: float | None = None  # None when limit is 0


# --- Line items ---
class LineItemBase(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class LineItemOut(LineItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --- Receipts ---
class ReceiptBase(BaseModel):
    merchant: str | None = None
    purchase_date: date | None = None
    total: Decimal | None = None
    currency: str | None = None
    category: str | None = None
    tax_amount: Decimal | None = None
    net_amount: Decimal | None = None
    fx_rate: Decimal | None = None
    fiscal_id: str | None = None


class ReceiptCreate(ReceiptBase):
    """Payload to save/correct a receipt after OCR review."""
    image_path: str | None = None
    raw_ocr_text: str | None = None
    line_items: list[LineItemBase] = []
    force: bool = False  # save even when a duplicate is detected


class ReceiptUpdate(BaseModel):
    """Partial update for an existing receipt (PATCH — all fields optional)."""
    merchant: str | None = None
    purchase_date: date | None = None
    total: Decimal | None = None
    currency: str | None = None
    category: str | None = None
    rotation: int | None = None
    tax_amount: Decimal | None = None
    net_amount: Decimal | None = None
    fx_rate: Decimal | None = None
    line_items: list[LineItemBase] | None = None


class ReceiptOut(ReceiptBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int | None = None
    owner_email: str | None = None
    image_path: str | None = None
    raw_ocr_text: str | None = None
    rotation: int = 0
    deleted_at: datetime | None = None  # set = receipt is in the Trash
    created_at: datetime
    line_items: list[LineItemOut] = []


class ReceiptPage(BaseModel):
    """One page of receipts plus totals across the whole filtered set."""
    items: list[ReceiptOut]
    total: int          # count of all matching receipts
    total_sum: Decimal  # raw sum (may mix currencies)
    normalized_sum: Decimal | None = None  # sum converted via fx_rate, when available
    limit: int
    offset: int


class ScanResult(BaseModel):
    """Returned right after upload+OCR, before the user confirms/saves."""
    image_path: str
    raw_ocr_text: str
    parsed: ReceiptCreate
    duplicates: list[ReceiptOut] = []


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
    change_pct: float | None = None


class ReceiptStats(BaseModel):
    total_spend: Decimal
    receipt_count: int
    recent_count: int = 0
    last_receipt_date: date | None = None
    by_category: list[CategoryStat] = []
    by_month: list[MonthStat] = []
    by_currency: list[CurrencyStat] = []
    top_merchants: list[MerchantStat] = []
    largest_receipt: LargestReceipt | None = None
    month_trend: MonthTrend | None = None
    budget_usage: list[BudgetUsage] = []


# --- Reports / analytics ---
class TimePoint(BaseModel):
    period: str  # "2026-06-12" (day) | "2026-W24" (week) | "2026-06" (month)
    total: Decimal
    count: int


class TimeSeries(BaseModel):
    granularity: str  # day | week | month
    date_from: date | None = None
    date_to: date | None = None
    total: Decimal = Decimal(0)
    points: list[TimePoint] = []


class RecurringMerchant(BaseModel):
    merchant: str
    category: str | None = None
    occurrences: int
    avg_amount: Decimal
    avg_interval_days: float
    last_date: date | None = None
    next_estimated: date | None = None


class DigestPreview(BaseModel):
    subject: str
    html: str
