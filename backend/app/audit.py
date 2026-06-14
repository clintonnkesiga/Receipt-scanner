"""Lightweight audit-log helper.  Call `record()` before committing the
transaction so the audit entry lands in the same DB transaction as the change.
"""
from sqlalchemy.orm import Session

from . import models


def record(
    db: Session,
    user: models.User | None,
    action: str,
    *,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        models.AuditLog(
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )
