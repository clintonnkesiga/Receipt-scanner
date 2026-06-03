import csv
import io
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..database import get_db
from ..ocr import run_ocr
from ..parser import parse_receipt
from ..security import get_current_user
from .. import models, schemas

# Every receipts endpoint requires a valid JWT.
router = APIRouter(
    prefix="/api/receipts",
    tags=["receipts"],
    dependencies=[Depends(get_current_user)],
)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/tiff"}


@router.post("/scan", response_model=schemas.ScanResult)
async def scan_receipt(file: UploadFile = File(...)):
    """Upload an image, run OCR + parsing, return parsed fields for review.

    Nothing is saved to the DB yet — the user confirms/corrects, then POSTs
    to the create endpoint below.
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"Unsupported file type: {file.content_type}")

    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.upload_dir, name)

    contents = await file.read()
    with open(path, "wb") as f:
        f.write(contents)

    raw_text = run_ocr(path)
    parsed = parse_receipt(raw_text)
    parsed.image_path = path

    return schemas.ScanResult(image_path=path, raw_ocr_text=raw_text, parsed=parsed)


@router.post("", response_model=schemas.ReceiptOut, status_code=201)
def create_receipt(payload: schemas.ReceiptCreate, db: Session = Depends(get_db)):
    """Persist a reviewed/corrected receipt."""
    receipt = models.Receipt(
        merchant=payload.merchant,
        purchase_date=payload.purchase_date,
        total=payload.total,
        currency=payload.currency,
        category=payload.category,
        image_path=payload.image_path,
        raw_ocr_text=payload.raw_ocr_text,
        line_items=[models.LineItem(**li.model_dump()) for li in payload.line_items],
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.get("", response_model=list[schemas.ReceiptOut])
def list_receipts(category: str | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Receipt).options(selectinload(models.Receipt.line_items))
    if category:
        stmt = stmt.where(models.Receipt.category == category)
    stmt = stmt.order_by(models.Receipt.created_at.desc())
    return db.scalars(stmt).all()


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db)):
    """Export all receipts (header-level) as CSV — handy for budgeting/taxes."""
    rows = db.scalars(select(models.Receipt).order_by(models.Receipt.purchase_date)).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "merchant", "purchase_date", "total", "currency", "category", "created_at"])
    for r in rows:
        writer.writerow([r.id, r.merchant, r.purchase_date, r.total, r.currency, r.category, r.created_at])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=receipts.csv"},
    )


@router.get("/{receipt_id}", response_model=schemas.ReceiptOut)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.get(models.Receipt, receipt_id)
    if receipt is None:
        raise HTTPException(404, "Receipt not found")
    return receipt


@router.delete("/{receipt_id}", status_code=204)
def delete_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.get(models.Receipt, receipt_id)
    if receipt is None:
        raise HTTPException(404, "Receipt not found")
    db.delete(receipt)
    db.commit()
