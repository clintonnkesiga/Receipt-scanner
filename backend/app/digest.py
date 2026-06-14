"""Weekly spend digest: builds an HTML summary per user and emails it.

Run as a scheduled job (cron / systemd timer / container scheduler):

    python -m app.digest            # send to all active users (needs SMTP)
    python -m app.digest --dry-run  # print who would be emailed, send nothing

Example weekly crontab entry (Mondays 07:00):

    0 7 * * 1  cd /app && /app/.venv/bin/python -m app.digest
"""
import argparse
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .email import email_configured, send_email, email_html
from . import models


def _fmt(n) -> str:
    return f"{Decimal(n or 0):,.0f}"


def _window_stats(db: Session, user_id: int, start: date, end: date):
    """(total, count) for receipts in [start, end] for a user."""
    R = models.Receipt
    return db.execute(
        select(func.coalesce(func.sum(R.total), 0), func.count(R.id)).where(
            R.owner_id == user_id,
            R.deleted_at.is_(None),
            R.purchase_date >= start,
            R.purchase_date <= end,
        )
    ).one()


def build_digest(db: Session, user: models.User, today: date | None = None) -> tuple[str, str]:
    """Build (subject, html) summarizing the user's last 7 days of spend."""
    today = today or date.today()
    start = today - timedelta(days=6)          # last 7 days inclusive
    prev_start = start - timedelta(days=7)
    prev_end = start - timedelta(days=1)
    R = models.Receipt

    total, count = _window_stats(db, user.id, start, today)
    prev_total, _ = _window_stats(db, user.id, prev_start, prev_end)

    change = None
    if prev_total:
        change = float((Decimal(total) - Decimal(prev_total)) / Decimal(prev_total) * 100)

    by_category = db.execute(
        select(R.category, func.coalesce(func.sum(R.total), 0), func.count(R.id))
        .where(R.owner_id == user.id, R.deleted_at.is_(None),
               R.purchase_date >= start, R.purchase_date <= today)
        .group_by(R.category)
        .order_by(func.coalesce(func.sum(R.total), 0).desc())
        .limit(5)
    ).all()

    top_merchants = db.execute(
        select(R.merchant, func.coalesce(func.sum(R.total), 0), func.count(R.id))
        .where(
            R.owner_id == user.id,
            R.deleted_at.is_(None),
            R.purchase_date >= start,
            R.purchase_date <= today,
            R.merchant.is_not(None),
            R.merchant != "",
        )
        .group_by(R.merchant)
        .order_by(func.coalesce(func.sum(R.total), 0).desc())
        .limit(5)
    ).all()

    from .config import settings

    span = f"{start.strftime('%b %-d')} – {today.strftime('%b %-d, %Y')}"
    subject = f"Your weekly spend: {_fmt(total)} ({count} receipt{'s' if count != 1 else ''})"

    if change is None:
        trend_html = '<span style="color:#64748b;">no prior week to compare</span>'
    elif change > 0:
        trend_html = f'<span style="color:#dc2626;">&#9650; {abs(change):.0f}% vs last week</span>'
    elif change < 0:
        trend_html = f'<span style="color:#059669;">&#9660; {abs(change):.0f}% vs last week</span>'
    else:
        trend_html = '<span style="color:#64748b;">flat vs last week</span>'

    def table_rows(items, label_idx=0):
        if not items:
            return '<tr><td style="padding:6px 0;color:#94a3b8;" colspan="2">No data</td></tr>'
        out = []
        for it in items:
            label = it[label_idx] or "—"
            out.append(
                f'<tr>'
                f'<td style="padding:7px 0;border-top:1px solid #f1f5f9;text-transform:capitalize;'
                f'font-size:14px;color:#0f172a;">{label}</td>'
                f'<td style="padding:7px 0;border-top:1px solid #f1f5f9;text-align:right;'
                f'font-size:14px;color:#0f172a;">{_fmt(it[1])}'
                f' <span style="color:#94a3b8;font-size:12px;">({it[2]})</span></td>'
                f'</tr>'
            )
        return "".join(out)

    # Stat card (total + trend) rendered as an inline HTML block inside body_lines
    stat_card = (
        f'<div style="background:#eff6ff;border:1px solid #dbeafe;border-radius:10px;'
        f'padding:16px 20px;margin:4px 0 20px;">'
        f'<div style="font-size:12px;font-weight:600;color:#1d4ed8;letter-spacing:0.05em;'
        f'text-transform:uppercase;margin-bottom:4px;">Total spend · {span}</div>'
        f'<div style="font-size:30px;font-weight:700;color:#0f172a;line-height:1.1;">{_fmt(total)}</div>'
        f'<div style="font-size:13px;color:#64748b;margin-top:6px;">'
        f'{trend_html}&nbsp;&nbsp;·&nbsp;&nbsp;{count} receipt{"s" if count != 1 else ""}'
        f'</div>'
        f'</div>'
    )

    cat_table = (
        f'<p style="margin:20px 0 6px;font-size:13px;font-weight:600;color:#64748b;'
        f'letter-spacing:0.05em;text-transform:uppercase;">By category</p>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;">{table_rows(by_category)}</table>'
    )

    merch_table = (
        f'<p style="margin:20px 0 6px;font-size:13px;font-weight:600;color:#64748b;'
        f'letter-spacing:0.05em;text-transform:uppercase;">Top merchants</p>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;">{table_rows(top_merchants)}</table>'
    )

    name = user.full_name or user.email
    html = email_html(
        heading="Your weekly spend summary",
        body_lines=[
            f"Hi {name}, here's how your spending looked over the past 7 days.",
            stat_card,
            cat_table,
            merch_table,
        ],
        cta_label="Open dashboard",
        cta_url=f"{settings.app_base_url}/dashboard",
        footer_note="You're receiving this weekly summary because you have a Receipt Scanner account.",
    )
    return subject, html


def send_weekly_digests(dry_run: bool = False) -> int:
    """Email every active user their weekly digest. Returns the count sent."""
    db = SessionLocal()
    sent = 0
    try:
        users = db.scalars(
            select(models.User).where(models.User.is_active.is_(True))
        ).all()
        for user in users:
            subject, html = build_digest(db, user)
            if dry_run:
                print(f"[dry-run] would email {user.email}: {subject}")
                continue
            try:
                send_email(user.email, subject, html)
                sent += 1
                print(f"✓ sent to {user.email}")
            except Exception as e:  # one bad address shouldn't stop the batch
                print(f"✗ failed for {user.email}: {e}")
    finally:
        db.close()
    return sent


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send the weekly spend digest.")
    parser.add_argument("--dry-run", action="store_true", help="Print, don't send.")
    args = parser.parse_args()
    if not args.dry_run and not email_configured():
        raise SystemExit("Email not configured — set SMTP_HOST in .env (or use --dry-run).")
    n = send_weekly_digests(dry_run=args.dry_run)
    if not args.dry_run:
        print(f"Done. Sent {n} digest(s).")
