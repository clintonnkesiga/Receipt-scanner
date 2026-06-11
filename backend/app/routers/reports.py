"""Analytics & reporting: time-series, recurring detection, exports, digest."""
import io
import statistics
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..digest import build_digest
from ..email import email_configured, send_email
from ..security import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/reports", tags=["reports"])

ELEVATED_ROLES = {"admin", "superadmin"}
GRANULARITIES = {"day", "week", "month"}


def _sees_all(user: models.User) -> bool:
    return user.role in ELEVATED_ROLES


def _scope(user: models.User) -> list:
    # Always exclude trashed (soft-deleted) receipts from reports/exports.
    conds = [models.Receipt.deleted_at.is_(None)]
    if not _sees_all(user):
        conds.append(models.Receipt.owner_id == user.id)
    return conds


@router.get("/timeseries", response_model=schemas.TimeSeries)
def timeseries(
    granularity: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Spend bucketed by day/week/month over an optional date range."""
    if granularity not in GRANULARITIES:
        granularity = "month"
    R = models.Receipt
    conds = [R.purchase_date.is_not(None), *_scope(current_user)]
    if date_from:
        conds.append(R.purchase_date >= date_from)
    if date_to:
        conds.append(R.purchase_date <= date_to)

    bucket = func.date_trunc(granularity, R.purchase_date)
    rows = db.execute(
        select(bucket.label("bucket"), func.coalesce(func.sum(R.total), 0), func.count(R.id))
        .where(*conds)
        .group_by(bucket)
        .order_by(bucket)
    ).all()

    points: list[schemas.TimePoint] = []
    grand = Decimal(0)
    for bkt, tot, cnt in rows:
        d = bkt.date() if hasattr(bkt, "date") else bkt
        if granularity == "day":
            label = d.isoformat()
        elif granularity == "week":
            iso = d.isocalendar()
            label = f"{iso.year}-W{iso.week:02d}"
        else:
            label = d.strftime("%Y-%m")
        points.append(schemas.TimePoint(period=label, total=tot, count=cnt))
        grand += Decimal(tot)

    return schemas.TimeSeries(
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
        total=grand,
        points=points,
    )


@router.get("/recurring", response_model=list[schemas.RecurringMerchant])
def recurring(
    min_occurrences: int = 3,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Merchants the user pays on a regular cadence (weekly..monthly-ish)."""
    R = models.Receipt
    conds = [
        R.merchant.is_not(None),
        R.merchant != "",
        R.purchase_date.is_not(None),
        *_scope(current_user),
    ]
    rows = db.execute(
        select(R.merchant, R.purchase_date, R.total, R.category)
        .where(*conds)
        .order_by(R.merchant, R.purchase_date)
    ).all()

    groups: dict[str, list] = defaultdict(list)
    for merchant, pdate, total, category in rows:
        groups[merchant.strip().lower()].append((merchant, pdate, total, category))

    out: list[schemas.RecurringMerchant] = []
    for entries in groups.values():
        if len(entries) < min_occurrences:
            continue
        dates = sorted(e[1] for e in entries)
        intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        intervals = [d for d in intervals if d > 0]  # drop same-day duplicates
        if not intervals:
            continue
        avg_interval = statistics.mean(intervals)
        # Regular cadence between ~weekly and ~monthly, with low variation.
        if not (5 <= avg_interval <= 45):
            continue
        if len(intervals) >= 2 and statistics.pstdev(intervals) > 0.6 * avg_interval:
            continue  # too irregular to call recurring

        amounts = [Decimal(e[2]) for e in entries if e[2] is not None]
        avg_amount = sum(amounts) / len(amounts) if amounts else Decimal(0)
        cats = [e[3] for e in entries if e[3]]
        category = max(set(cats), key=cats.count) if cats else None
        last_date = dates[-1]
        from datetime import timedelta
        next_est = last_date + timedelta(days=round(avg_interval))

        out.append(schemas.RecurringMerchant(
            merchant=entries[0][0],
            category=category,
            occurrences=len(entries),
            avg_amount=avg_amount,
            avg_interval_days=round(avg_interval, 1),
            last_date=last_date,
            next_estimated=next_est,
        ))

    out.sort(key=lambda r: r.occurrences, reverse=True)
    return out


def _export_rows(db: Session, user: models.User, date_from, date_to):
    R = models.Receipt
    conds = list(_scope(user))
    if date_from:
        conds.append(R.purchase_date >= date_from)
    if date_to:
        conds.append(R.purchase_date <= date_to)
    from sqlalchemy.orm import selectinload
    return db.scalars(
        select(R).where(*conds)
        .options(selectinload(R.owner))
        .order_by(R.purchase_date.asc().nullslast(), R.id)
    ).all()


_HEADERS = ["ID", "Owner", "Merchant", "Date", "Total", "Tax", "Net",
            "Currency", "FX rate", "Category", "Created"]


def _row_values(r: models.Receipt) -> list:
    return [
        r.id, r.owner_email, r.merchant,
        r.purchase_date.isoformat() if r.purchase_date else "",
        r.total, r.tax_amount, r.net_amount, r.currency, r.fx_rate, r.category,
        r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
    ]


@router.get("/export.xlsx")
def export_xlsx(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    rows = _export_rows(db, current_user, date_from, date_to)
    wb = Workbook()
    ws = wb.active
    ws.title = "Receipts"
    ws.append(_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for r in rows:
        ws.append([(float(v) if isinstance(v, Decimal) else v) for v in _row_values(r)])
    # Roomy column widths.
    for i, _ in enumerate(_HEADERS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = 16

    buf = io.BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=receipts.xlsx"},
    )


@router.get("/export.pdf")
def export_pdf(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    rows = _export_rows(db, current_user, date_from, date_to)
    # Drop a couple of wide columns to fit the page (Owner, Created).
    cols = ["ID", "Merchant", "Date", "Total", "Tax", "Net", "Currency", "Category"]
    keep = [0, 2, 3, 4, 5, 6, 7, 9]  # indices into _row_values

    grand = sum((Decimal(r.total) for r in rows if r.total is not None), Decimal(0))
    span = ""
    if date_from or date_to:
        span = f" ({date_from or '…'} to {date_to or '…'})"

    data = [cols]
    for r in rows:
        vals = _row_values(r)
        data.append([("" if vals[i] is None else str(vals[i])) for i in keep])

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title="Receipts")
    styles = getSampleStyleSheet()
    elems = [
        Paragraph(f"Receipts export{span}", styles["Title"]),
        Paragraph(f"{len(rows)} receipts · total {grand:,.2f}", styles["Normal"]),
        Spacer(1, 12),
    ]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("ALIGN", (3, 1), (5, -1), "RIGHT"),
    ]))
    elems.append(table)
    doc.build(elems)
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=receipts.pdf"},
    )


@router.get("/digest/preview", response_model=schemas.DigestPreview)
def digest_preview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Render the weekly digest for the current user (no email sent)."""
    subject, html = build_digest(db, current_user)
    return schemas.DigestPreview(subject=subject, html=html)


@router.post("/digest/send", status_code=204)
def digest_send(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Email the current user their weekly digest now (requires SMTP config)."""
    if not email_configured():
        raise HTTPException(400, "Email is not configured on the server (set SMTP_HOST).")
    subject, html = build_digest(db, current_user)
    try:
        send_email(current_user.email, subject, html)
    except Exception as e:
        raise HTTPException(502, f"Could not send email: {e}")
