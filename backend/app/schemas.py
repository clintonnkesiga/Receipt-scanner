from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr


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


class ReceiptOut(ReceiptBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_path: str | None = None
    raw_ocr_text: str | None = None
    created_at: datetime
    line_items: list[LineItemOut] = []


class ScanResult(BaseModel):
    """Returned right after upload+OCR, before the user confirms/saves."""
    image_path: str
    raw_ocr_text: str
    parsed: ReceiptCreate
