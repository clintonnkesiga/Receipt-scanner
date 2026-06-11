import csv
import io
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..database import get_db
from .. import audit as audit_mod
from ..ocr import run_ocr
from ..parser import parse_receipt
from ..security import get_current_user
from .. import models, schemas, storage

# Every receipts endpoint requires a valid JWT.
router = APIRouter(prefix="/api/receipts", tags=["receipts"])

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/tiff",
    "application/pdf",
}

# Roles that can see/manage every user's receipts.
ELEVATED_ROLES = {"admin", "superadmin"}


def _sees_all(user: models.User) -> bool:
    return user.role in ELEVATED_ROLES


# Max absolute value storable in the amount columns: NUMERIC(14,2) -> < 10^12.
_MONEY_MAX = Decimal(10) ** 12
_QTY_MAX = Decimal(10) ** 9  # quantity is NUMERIC(12,3) -> < 10^9


def _fit(value: Decimal | None, max_abs: Decimal = _MONEY_MAX) -> Decimal | None:
    """Drop OCR-garbage numbers that would overflow the DB column (store NULL)
    instead of 500-ing the whole save."""
    if value is None:
        return None
    try:
        return value if abs(value) < max_abs else None
    except (TypeError, ArithmeticError):
        return None


# How close two same-merchant, same-total receipts must be (in days) to count
# as duplicates when no fiscal id is available — absorbs OCR date wobble.
_DUP_DATE_WINDOW = timedelta(days=3)


def _find_duplicates(
    db: Session,
    owner_id: int,
    *,
    merchant: str | None,
    purchase_date,
    total: Decimal | None,
    fiscal_id: str | None,
    exclude_id: int | None = None,
    limit: int = 5,
) -> list[models.Receipt]:
    """Find likely duplicates of a receipt for one owner.

    Strong signal: same `fiscal_id` (the unique transaction number printed on
    the receipt) — immune to OCR date/total errors. Fallback when there's no
    fiscal id: same merchant + same total within a few days.
    """
    R = models.Receipt
    base = [R.owner_id == owner_id, R.deleted_at.is_(None)]
    if exclude_id is not None:
        base.append(R.id != exclude_id)
    opts = (selectinload(R.line_items), selectinload(R.owner))

    if fiscal_id:
        rows = db.scalars(
            select(R).where(*base, R.fiscal_id == fiscal_id).options(*opts).limit(limit)
        ).all()
        if rows:
            return list(rows)

    if merchant and total is not None:
        conds = [*base, R.merchant.ilike(merchant), R.total == total]
        if purchase_date:
            conds.append(R.purchase_date >= purchase_date - _DUP_DATE_WINDOW)
            conds.append(R.purchase_date <= purchase_date + _DUP_DATE_WINDOW)
        return list(
            db.scalars(select(R).where(*conds).options(*opts).limit(limit)).all()
        )

    return []


@router.post("/scan", response_model=schemas.ScanResult)
async def scan_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Upload an image, run OCR + parsing, return parsed fields for review.

    Nothing is saved to the DB yet — the user confirms/corrects, then POSTs
    to the create endpoint below.
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"Unsupported file type: {file.content_type}")

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    contents = await file.read()

    # OCR requires a real filesystem path; use a temp file then clean up.
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    try:
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(contents)
        raw_text = run_ocr(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    filer_path = await storage.upload(contents, file.filename or f"receipt{ext}", current_user.id)
    parsed = parse_receipt(raw_text)
    parsed.image_path = filer_path

    duplicates = _find_duplicates(
        db, current_user.id,
        merchant=parsed.merchant,
        purchase_date=parsed.purchase_date,
        total=parsed.total,
        fiscal_id=parsed.fiscal_id,
    )

    return schemas.ScanResult(
        image_path=filer_path,
        raw_ocr_text=raw_text,
        parsed=parsed,
        duplicates=duplicates,
    )


@router.post("", response_model=schemas.ReceiptOut, status_code=201)
def create_receipt(
    payload: schemas.ReceiptCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Persist a reviewed/corrected receipt, owned by the current user."""
    # Block likely duplicates unless the user explicitly overrode (force=True).
    if not payload.force:
        dups = _find_duplicates(
            db, current_user.id,
            merchant=payload.merchant,
            purchase_date=payload.purchase_date,
            total=payload.total,
            fiscal_id=payload.fiscal_id,
        )
        if dups:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "duplicate_receipt",
                    "message": "This looks like a receipt you already saved.",
                    "duplicate_ids": [d.id for d in dups],
                },
            )

    receipt = models.Receipt(
        owner_id=current_user.id,
        merchant=payload.merchant,
        purchase_date=payload.purchase_date,
        total=_fit(payload.total),
        currency=payload.currency,
        category=payload.category,
        image_path=payload.image_path,
        raw_ocr_text=payload.raw_ocr_text,
        fiscal_id=payload.fiscal_id,
        tax_amount=_fit(payload.tax_amount),
        net_amount=_fit(payload.net_amount),
        fx_rate=payload.fx_rate,
        line_items=[
            models.LineItem(
                description=li.description,
                quantity=_fit(li.quantity, _QTY_MAX),
                unit_price=_fit(li.unit_price),
                amount=_fit(li.amount),
            )
            for li in payload.line_items
        ],
    )
    db.add(receipt)
    audit_mod.record(db, current_user, "receipt.create", target_type="receipt",
                     detail=receipt.merchant or "—")
    db.commit()
    db.refresh(receipt)
    return receipt


@router.get("", response_model=schemas.ReceiptPage)
def list_receipts(
    q: str | None = None,
    category: str | None = None,
    sort: str = "date_desc",
    limit: int = 20,
    offset: int = 0,
    date_from: date | None = None,
    date_to: date | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """A page of receipts with server-side search/filter/sort/date-range/amount-range."""
    R = models.Receipt
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    conds = [R.deleted_at.is_(None)]  # exclude trashed receipts
    if not _sees_all(current_user):
        conds.append(R.owner_id == current_user.id)
    if category:
        conds.append(R.category == category)
    if q:
        conds.append(R.merchant.ilike(f"%{q}%"))
    if date_from:
        conds.append(R.purchase_date >= date_from)
    if date_to:
        conds.append(R.purchase_date <= date_to)
    if amount_min is not None:
        conds.append(R.total >= amount_min)
    if amount_max is not None:
        conds.append(R.total <= amount_max)

    # Count + sum over the full filtered set (drives totals + pagination).
    total, total_sum = db.execute(
        select(func.count(R.id), func.coalesce(func.sum(R.total), 0)).where(*conds)
    ).one()

    # Normalized sum: convert via fx_rate where available, fall back to raw total.
    normalized_sum = db.execute(
        select(func.coalesce(
            func.sum(func.coalesce(R.total * R.fx_rate, R.total)), 0
        )).where(*conds)
    ).scalar_one()

    order = {
        "date_desc": R.purchase_date.desc().nullslast(),
        "date_asc": R.purchase_date.asc().nullslast(),
        "total_desc": R.total.desc().nullslast(),
        "total_asc": R.total.asc().nullslast(),
    }.get(sort, R.purchase_date.desc().nullslast())

    items = db.scalars(
        select(R)
        .where(*conds)
        .options(selectinload(R.line_items), selectinload(R.owner))
        .order_by(order, R.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return schemas.ReceiptPage(
        items=items,
        total=total,
        total_sum=total_sum,
        normalized_sum=normalized_sum,
        limit=limit,
        offset=offset,
    )


@router.get("/export.csv")
def export_csv(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Export receipts (header-level) as CSV — handy for budgeting/taxes."""
    stmt = (
        select(models.Receipt)
        .where(models.Receipt.deleted_at.is_(None))  # exclude trashed receipts
        .options(selectinload(models.Receipt.owner))
        .order_by(models.Receipt.purchase_date)
    )
    if not _sees_all(current_user):
        stmt = stmt.where(models.Receipt.owner_id == current_user.id)
    rows = db.scalars(stmt).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "owner", "merchant", "purchase_date", "total", "currency", "category", "created_at"])
    for r in rows:
        writer.writerow([r.id, r.owner_email, r.merchant, r.purchase_date, r.total, r.currency, r.category, r.created_at])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=receipts.csv"},
    )


@router.get("/stats", response_model=schemas.ReceiptStats)
def stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Aggregated spend for the dashboard, scoped to what the user may see."""
    R = models.Receipt
    scope = [] if _sees_all(current_user) else [R.owner_id == current_user.id]
    scope.append(R.deleted_at.is_(None))  # exclude trashed receipts from all stats
    total = func.coalesce(func.sum(R.total), 0)

    overall = db.execute(
        select(total, func.count(R.id)).where(*scope)
    ).one()

    by_category = db.execute(
        select(R.category, total, func.count(R.id))
        .where(*scope)
        .group_by(R.category)
        .order_by(total.desc())
    ).all()

    by_currency = db.execute(
        select(R.currency, total, func.count(R.id))
        .where(*scope)
        .group_by(R.currency)
        .order_by(total.desc())
    ).all()

    month = func.to_char(R.purchase_date, "YYYY-MM")
    by_month = db.execute(
        select(month, total, func.count(R.id))
        .where(*scope, R.purchase_date.is_not(None))
        .group_by(month)
        .order_by(month)
    ).all()

    top_merchants = db.execute(
        select(R.merchant, total, func.count(R.id))
        .where(*scope, R.merchant.is_not(None), R.merchant != "")
        .group_by(R.merchant)
        .order_by(total.desc())
        .limit(8)
    ).all()

    largest = db.execute(
        select(R.id, R.merchant, R.total, R.currency, R.purchase_date)
        .where(*scope, R.total.is_not(None))
        .order_by(R.total.desc())
        .limit(1)
    ).first()

    # Recent activity: receipts created in the last 30 days, and the most
    # recent purchase date on record.
    since = datetime.now(timezone.utc) - timedelta(days=30)
    recent_count = db.execute(
        select(func.count(R.id)).where(*scope, R.created_at >= since)
    ).scalar_one()
    last_receipt_date = db.execute(
        select(func.max(R.purchase_date)).where(*scope)
    ).scalar_one()

    # Month-over-month trend, keyed off calendar months from by_month.
    month_totals = {m: t for m, t, _ in by_month}
    today = date.today()
    cur_key = today.strftime("%Y-%m")
    prev_key = today.replace(day=1) - timedelta(days=1)
    prev_key = prev_key.strftime("%Y-%m")
    cur = Decimal(month_totals.get(cur_key, 0))
    prev = Decimal(month_totals.get(prev_key, 0))
    change_pct = float((cur - prev) / prev * 100) if prev else None
    month_trend = schemas.MonthTrend(current=cur, previous=prev, change_pct=change_pct)

    # Budget usage for the current calendar month.
    budgets = db.scalars(
        select(models.Budget).where(models.Budget.owner_id == current_user.id)
    ).all()
    cur_month_start = today.replace(day=1)
    budget_usage = []
    for b in budgets:
        spent_conds = [
            models.Receipt.owner_id == current_user.id,
            models.Receipt.deleted_at.is_(None),
            models.Receipt.purchase_date >= cur_month_start,
            models.Receipt.purchase_date <= today,
        ]
        if b.category is not None:
            spent_conds.append(models.Receipt.category == b.category)
        spent = db.execute(
            select(func.coalesce(func.sum(models.Receipt.total), 0)).where(*spent_conds)
        ).scalar_one()
        pct = float(spent / b.monthly_limit * 100) if b.monthly_limit else None
        budget_usage.append(schemas.BudgetUsage(
            budget=schemas.BudgetOut.model_validate(b),
            spent=spent,
            pct=pct,
        ))

    return schemas.ReceiptStats(
        total_spend=overall[0],
        receipt_count=overall[1],
        recent_count=recent_count,
        last_receipt_date=last_receipt_date,
        by_category=[
            schemas.CategoryStat(category=c, total=t, count=n) for c, t, n in by_category
        ],
        by_currency=[
            schemas.CurrencyStat(currency=c, total=t, count=n) for c, t, n in by_currency
        ],
        by_month=[
            schemas.MonthStat(month=m, total=t, count=n) for m, t, n in by_month
        ],
        top_merchants=[
            schemas.MerchantStat(merchant=m, total=t, count=n) for m, t, n in top_merchants
        ],
        largest_receipt=(
            schemas.LargestReceipt(
                id=largest[0],
                merchant=largest[1],
                total=largest[2],
                currency=largest[3],
                purchase_date=largest[4],
            )
            if largest
            else None
        ),
        month_trend=month_trend,
        budget_usage=budget_usage,
    )


def _get_owned_or_404(
    receipt_id: int, db: Session, user: models.User, active_only: bool = False
) -> models.Receipt:
    """Fetch a receipt the user is allowed to see, else 404 (don't leak existence).

    When ``active_only`` is set, a trashed (soft-deleted) receipt also 404s — used
    by the edit/rescan/image paths that should never operate on Trash contents.
    """
    receipt = db.get(models.Receipt, receipt_id)
    if receipt is None:
        raise HTTPException(404, "Receipt not found")
    if not _sees_all(user) and receipt.owner_id != user.id:
        raise HTTPException(404, "Receipt not found")
    if active_only and receipt.deleted_at is not None:
        raise HTTPException(404, "Receipt not found")
    return receipt


@router.get("/trash", response_model=schemas.ReceiptPage)
def list_trash(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Receipts the user has soft-deleted, most-recently-trashed first."""
    R = models.Receipt
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    conds = [R.deleted_at.is_not(None)]
    if not _sees_all(current_user):
        conds.append(R.owner_id == current_user.id)

    total, total_sum = db.execute(
        select(func.count(R.id), func.coalesce(func.sum(R.total), 0)).where(*conds)
    ).one()

    items = db.scalars(
        select(R)
        .where(*conds)
        .options(selectinload(R.line_items), selectinload(R.owner))
        .order_by(R.deleted_at.desc(), R.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return schemas.ReceiptPage(
        items=items,
        total=total,
        total_sum=total_sum,
        normalized_sum=None,
        limit=limit,
        offset=offset,
    )


@router.get("/{receipt_id}", response_model=schemas.ReceiptOut)
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_or_404(receipt_id, db, current_user)


@router.get("/{receipt_id}/image")
async def get_receipt_image(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Serve the stored receipt image to its owner (or an admin)."""
    receipt = _get_owned_or_404(receipt_id, db, current_user)  # trashed images still viewable
    if not receipt.image_path:
        raise HTTPException(404, "No image for this receipt")
    try:
        data, content_type = await storage.stream(receipt.image_path)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(404, "No image for this receipt")
        raise HTTPException(502, "Storage error")
    return Response(content=data, media_type=content_type)


@router.patch("/{receipt_id}", response_model=schemas.ReceiptOut)
def update_receipt(
    receipt_id: int,
    payload: schemas.ReceiptUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Partially update a receipt's editable fields, including line items."""
    receipt = _get_owned_or_404(receipt_id, db, current_user, active_only=True)
    update_data = payload.model_dump(exclude_unset=True)

    # Replace line items wholesale when provided.
    if "line_items" in update_data:
        receipt.line_items = [
            models.LineItem(
                description=li["description"],
                quantity=_fit(li.get("quantity"), _QTY_MAX),
                unit_price=_fit(li.get("unit_price")),
                amount=_fit(li.get("amount")),
            )
            for li in update_data.pop("line_items")
        ]

    if "total" in update_data:
        update_data["total"] = _fit(update_data["total"])
    for field, value in update_data.items():
        setattr(receipt, field, value)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/{receipt_id}/rescan", response_model=schemas.ScanResult)
async def rescan_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Re-fetch the stored image, re-run OCR, and return fresh parsed fields.

    Updates raw_ocr_text in the DB but does NOT overwrite the user-reviewed
    fields — the caller reviews the new result before deciding to apply it.
    """
    receipt = _get_owned_or_404(receipt_id, db, current_user, active_only=True)
    if not receipt.image_path:
        raise HTTPException(404, "No image for this receipt")

    try:
        data, _ = await storage.stream(receipt.image_path)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(404, "Image not found in storage")
        raise HTTPException(502, "Storage error")

    ext = os.path.splitext(receipt.image_path)[1] or ".jpg"
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    try:
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(data)
        raw_text = run_ocr(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    receipt.raw_ocr_text = raw_text
    db.commit()

    parsed = parse_receipt(raw_text)
    parsed.image_path = receipt.image_path
    return schemas.ScanResult(image_path=receipt.image_path, raw_ocr_text=raw_text, parsed=parsed)


@router.delete("/{receipt_id}", status_code=204)
def delete_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Soft-delete: move the receipt to the Trash (recoverable). The stored image
    is kept so a restore can bring it back intact."""
    receipt = _get_owned_or_404(receipt_id, db, current_user, active_only=True)
    receipt.deleted_at = datetime.now(timezone.utc)
    audit_mod.record(db, current_user, "receipt.delete", target_type="receipt",
                     target_id=receipt_id, detail=receipt.merchant or "—")
    db.commit()


@router.post("/{receipt_id}/restore", response_model=schemas.ReceiptOut)
def restore_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Bring a trashed receipt back to the active list."""
    receipt = _get_owned_or_404(receipt_id, db, current_user)
    if receipt.deleted_at is None:
        raise HTTPException(409, "Receipt is not in the Trash")
    receipt.deleted_at = None
    audit_mod.record(db, current_user, "receipt.restore", target_type="receipt",
                     target_id=receipt_id, detail=receipt.merchant or "—")
    db.commit()
    db.refresh(receipt)
    return receipt


@router.delete("/{receipt_id}/permanent", status_code=204)
async def permanently_delete_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Hard-delete a receipt that's already in the Trash, and remove its stored
    image from SeaweedFS. Irreversible."""
    receipt = _get_owned_or_404(receipt_id, db, current_user)
    if receipt.deleted_at is None:
        raise HTTPException(409, "Move the receipt to the Trash before deleting it permanently")
    filer_path = receipt.image_path
    audit_mod.record(db, current_user, "receipt.purge", target_type="receipt",
                     target_id=receipt_id, detail=receipt.merchant or "—")
    db.delete(receipt)
    db.commit()
    # Best-effort cleanup of the file in SeaweedFS.
    if filer_path:
        try:
            await storage.delete(filer_path)
        except Exception:
            pass
