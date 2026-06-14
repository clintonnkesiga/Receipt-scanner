"""Read-only audit log endpoint."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=schemas.AuditPage)
def list_audit(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return the audit log.

    Regular users see only their own entries; admins and superadmins see all.
    """
    base = select(models.AuditLog)
    count_q = select(func.count()).select_from(models.AuditLog)

    if current_user.role not in ("admin", "superadmin"):
        base = base.where(models.AuditLog.user_id == current_user.id)
        count_q = count_q.where(models.AuditLog.user_id == current_user.id)

    total = db.scalar(count_q)
    items = db.scalars(
        base.order_by(models.AuditLog.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return schemas.AuditPage(items=items, total=total)
