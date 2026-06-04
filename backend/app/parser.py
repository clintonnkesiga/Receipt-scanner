"""Rules-based extraction of structured fields from raw OCR text.

Receipts are semi-structured, so heuristics get you a long way. Tune the
keyword lists and patterns to the specific stores you actually shop at.
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .schemas import ReceiptCreate, LineItemBase

# Keywords that hint at a receipt's category.
FUEL_HINTS = ("fuel", "petrol", "diesel", "unleaded", "litre", "liter", "shell",
              "total energies", "engen", "gas station", "pump")
GROCERY_HINTS = ("supermarket", "mart", "grocery", "store", "qty", "vat", "cashier")

# Lines containing these usually hold the grand total.
TOTAL_KEYWORDS = ("grand total", "total due", "amount due", "total", "balance")

# Grab a full number run including thousands/decimal separators, e.g.
# "150,450", "1,234.56", "12.50", "127500". _to_decimal() then disambiguates
# whether a separator is a thousands marker or a decimal point.
MONEY = r"\d[\d.,]*\d"

DATE_PATTERNS = [
    (r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", "%Y-%m-%d"),
    (r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", "%d-%m-%Y"),
    (r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})\b", "%d-%m-%y"),
]

# Unambiguous textual currency markers (ISO codes / local spellings). Checked
# first, in order, so a local marker wins over a noisy symbol elsewhere.
CURRENCY_WORDS = {
    "UGX": "UGX", "USHS": "UGX", "USH": "UGX", "SHS": "UGX", "USD": "USD",
    "KES": "KES", "EUR": "EUR", "GBP": "GBP",
}

# Currency symbols. Only honoured when adjacent to a number (e.g. "$12.50"),
# since a lone symbol is usually OCR noise on a local-currency receipt.
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}

# Fallback when no currency marker is found on the receipt (most are local).
DEFAULT_CURRENCY = "UGX"


def _to_decimal(raw: str) -> Decimal | None:
    s = raw.strip()
    # Normalise thousands/decimal separators to a plain "1234.56".
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) == 2 else s.replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _looks_like_money(token: str) -> bool:
    """Reject long all-digit runs — phone numbers, account/reference IDs —
    which OCR on statements/receipts otherwise mistakes for amounts."""
    digits = re.sub(r"\D", "", token)
    if "." not in token and "," not in token and len(digits) >= 10:
        return False
    return True


def _money_tokens(line: str) -> list[str]:
    return [m for m in re.findall(MONEY, line) if _looks_like_money(m)]


def _find_total(lines: list[str]) -> Decimal | None:
    candidate = None
    for line in lines:
        low = line.lower()
        if any(k in low for k in TOTAL_KEYWORDS):
            amounts = _money_tokens(line)
            if amounts:
                val = _to_decimal(amounts[-1])
                if val is not None:
                    candidate = val
    if candidate is not None:
        return candidate
    # Fallback: the largest money value anywhere on the receipt. Skip bare
    # year-like integers (e.g. a date's "2026") so they aren't read as totals.
    all_amounts = []
    for line in lines:
        for m in _money_tokens(line):
            val = _to_decimal(m)
            if val is None:
                continue
            if "." not in m and "," not in m and 1900 <= val <= 2099:
                continue
            all_amounts.append(val)
    return max(all_amounts) if all_amounts else None


def _find_date(text: str) -> date | None:
    for pattern, fmt in DATE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            try:
                parts = "-".join(m.groups())
                return datetime.strptime(parts, fmt).date()
            except ValueError:
                continue
    return None


def _find_currency(text: str) -> str:
    upper = text.upper()
    # 1) Trust an explicit word/ISO marker first (word-boundary, so "USD" isn't
    #    matched inside another token).
    for word, code in CURRENCY_WORDS.items():
        if re.search(rf"\b{word}\b", upper):
            return code
    # 2) Otherwise accept a symbol only when it sits next to a number.
    for sym, code in CURRENCY_SYMBOLS.items():
        if re.search(rf"{re.escape(sym)}\s*\d|\d\s*{re.escape(sym)}", upper):
            return code
    return DEFAULT_CURRENCY


def _find_merchant(lines: list[str]) -> str | None:
    # Heuristic: the first non-empty line with letters is usually the store name.
    for line in lines:
        stripped = line.strip()
        if len(stripped) >= 3 and re.search(r"[A-Za-z]", stripped):
            return stripped[:255]
    return None


def _categorize(text: str) -> str:
    low = text.lower()
    fuel = sum(h in low for h in FUEL_HINTS)
    grocery = sum(h in low for h in GROCERY_HINTS)
    if fuel > grocery and fuel > 0:
        return "fuel"
    if grocery > 0:
        return "grocery"
    return "other"


def _find_line_items(lines: list[str]) -> list[LineItemBase]:
    """Grab 'description .... amount' style rows, skipping total/subtotal lines."""
    items: list[LineItemBase] = []
    skip = TOTAL_KEYWORDS + ("subtotal", "change", "cash", "vat", "tax", "tendered")
    for line in lines:
        low = line.lower()
        if any(k in low for k in skip):
            continue
        amounts = _money_tokens(line)
        if not amounts:
            continue
        desc = re.sub(MONEY, "", line).strip(" .-\t")
        if len(desc) < 2:
            continue
        items.append(LineItemBase(description=desc[:255], amount=_to_decimal(amounts[-1])))
    return items


def parse_receipt(raw_text: str) -> ReceiptCreate:
    lines = [l for l in raw_text.splitlines() if l.strip()]
    return ReceiptCreate(
        merchant=_find_merchant(lines),
        purchase_date=_find_date(raw_text),
        total=_find_total(lines),
        currency=_find_currency(raw_text),
        category=_categorize(raw_text),
        raw_ocr_text=raw_text,
        line_items=_find_line_items(lines),
    )
