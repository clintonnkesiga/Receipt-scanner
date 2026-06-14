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

# Lines that contain "total" but are NOT the grand total — tender/change/tax
# rows. "Tendered Total 50,000" must not be mistaken for the bill total.
NON_TOTAL_HINTS = ("subtotal", "sub total", "tendered", "tender", "change",
                   "cash", "card", "tax", "vat", "balance due")

# Keywords that flag a tax / VAT line.
TAX_KEYWORDS = ("vat", "tax", "gst", "hst", "pst", "tva", "mwst", "iva")

# Labels (in priority order) that precede a receipt's unique transaction id.
# Used for reliable duplicate detection — far more stable than date/total.
FISCAL_LABELS = (
    r"fiscal\s*doc(?:ument)?\s*(?:no|number|#)?",
    r"\bfdn\b",
    r"cash\s*sale\s*(?:no|number|#)?",
    r"receipt\s*(?:no|number|#)",
    r"invoice\s*(?:no|number|#)",
    r"verification\s*code",
)

# Grab a full number run including thousands/decimal separators, e.g.
# "150,450", "1,234.56", "12.50", "127500". _to_decimal() then disambiguates
# whether a separator is a thousands marker or a decimal point.
MONEY = r"\d[\d.,]*\d"

DATE_PATTERNS = [
    (r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", "%Y-%m-%d"),
    (r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", "%d-%m-%Y"),
    (r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})\b", "%d-%m-%y"),
]

# Month names → number, for textual dates like "17 Mar 2026" or "Mar 17, 2026".
MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}

TEXT_DATE_PATTERNS = [
    (r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\,?\s+(\d{4})\b", "dmy"),  # 17 Mar 2026
    (r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})\,?\s+(\d{4})\b", "mdy"),  # Mar 17, 2026
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
        # Skip tender/change/tax rows that also contain the word "total".
        if any(k in low for k in NON_TOTAL_HINTS):
            continue
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
    # Numeric formats first. finditer (not search) so a non-date match like a
    # time "13.33.23" doesn't abort the whole pattern.
    for pattern, fmt in DATE_PATTERNS:
        for m in re.finditer(pattern, text):
            try:
                return datetime.strptime("-".join(m.groups()), fmt).date()
            except ValueError:
                continue
    # Then textual months, e.g. "17 Mar 2026".
    for pattern, order in TEXT_DATE_PATTERNS:
        for m in re.finditer(pattern, text):
            a, b, year = m.groups()
            day, mon = (a, b) if order == "dmy" else (b, a)
            month = MONTHS.get(mon[:3].lower())
            if not month:
                continue
            try:
                return date(int(year), month, int(day))
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
    # The store name is near the top. Prefer the first of the leading lines that
    # has a real word (>=4 letters) so OCR noise above the logo (e.g. "WA et")
    # is skipped rather than taken as the name.
    for line in lines[:6]:
        stripped = line.strip()
        if re.search(r"[A-Za-z]{4,}", stripped):
            return stripped[:255]
    # Fallback: the first line with any letters at all.
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


def _find_tax_amount(lines: list[str]) -> Decimal | None:
    """Return the first money value on a line that contains a tax/VAT keyword."""
    for line in lines:
        low = line.lower()
        if any(k in low for k in TAX_KEYWORDS):
            amounts = _money_tokens(line)
            if amounts:
                val = _to_decimal(amounts[-1])
                if val is not None:
                    return val
    return None


# Transaction numbers are commonly a 4-digit year, a dash, then digits
# (e.g. "2026-1550307"). This survives OCR even when the *label* is mangled
# (we've seen "CashSale" read as "MbashSale"), so it's a reliable fallback key.
TXN_NUMBER_RE = re.compile(r"\b(20\d{2}-\d{4,})\b")


def _find_fiscal_id(text: str) -> str | None:
    """Extract a receipt's unique transaction id (fiscal doc / cash-sale /
    receipt / invoice number, or verification code) for duplicate detection."""
    # OCR sometimes reads the hyphen in "2026-1550307" as an en/em dash; fold
    # them to a plain hyphen so the patterns below match.
    text = re.sub(r"[‒–—―−]", "-", text)
    # 1) Labeled ids — most authoritative when the label survives OCR.
    for label in FISCAL_LABELS:
        m = re.search(label + r"[:.\s#=-]*([A-Za-z0-9][A-Za-z0-9\-]{5,})", text, re.IGNORECASE)
        if m:
            token = m.group(1).upper().strip("-")
            # Require enough alphanumerics to be a real id, not OCR noise.
            if len(re.sub(r"[^A-Za-z0-9]", "", token)) >= 6:
                return token[:64]
    # 2) Year-prefixed transaction number anywhere (catches OCR-garbled labels).
    m = TXN_NUMBER_RE.search(text)
    if m:
        return m.group(1).upper()[:64]
    return None


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
    total = _find_total(lines)
    tax_amount = _find_tax_amount(lines)
    net_amount = (total - tax_amount) if (total is not None and tax_amount is not None) else None
    return ReceiptCreate(
        merchant=_find_merchant(lines),
        purchase_date=_find_date(raw_text),
        total=total,
        currency=_find_currency(raw_text),
        category=_categorize(raw_text),
        raw_ocr_text=raw_text,
        line_items=_find_line_items(lines),
        tax_amount=tax_amount,
        net_amount=net_amount,
        fiscal_id=_find_fiscal_id(raw_text),
    )
