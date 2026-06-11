from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user
from .. import models, schemas, audit

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


def _get_owned_or_404(budget_id: int, db: Session, user: models.User) -> models.Budget:
    b = db.get(models.Budget, budget_id)
    if b is None or b.owner_id != user.id:
        raise HTTPException(404, "Budget not found")
    return b


@router.get("", response_model=list[schemas.BudgetOut])
def list_budgets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.scalars(
        select(models.Budget)
        .where(models.Budget.owner_id == current_user.id)
        .order_by(models.Budget.category.nullsfirst(), models.Budget.id)
    ).all()


@router.post("", response_model=schemas.BudgetOut, status_code=201)
def create_budget(
    payload: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Enforce one budget per (owner, category) slot.
    existing = db.scalar(
        select(models.Budget).where(
            models.Budget.owner_id == current_user.id,
            models.Budget.category == payload.category,
        )
    )
    if existing:
        raise HTTPException(409, "A budget for this category already exists")
    b = models.Budget(
        owner_id=current_user.id,
        category=payload.category,
        monthly_limit=payload.monthly_limit,
        currency=payload.currency,
    )
    db.add(b)
    audit.record(db, current_user, "budget.create", target_type="budget",
                 detail=b.category or "all categories")
    db.commit()
    db.refresh(b)
    return b


@router.patch("/{budget_id}", response_model=schemas.BudgetOut)
def update_budget(
    budget_id: int,
    payload: schemas.BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    b = _get_owned_or_404(budget_id, db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(b, field, value)
    db.commit()
    db.refresh(b)
    return b


@router.delete("/{budget_id}", status_code=204)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    b = _get_owned_or_404(budget_id, db, current_user)
    audit.record(db, current_user, "budget.delete", target_type="budget",
                 target_id=budget_id, detail=b.category or "all categories")
    db.delete(b)
    db.commit()


@router.get("/usage", response_model=list[schemas.BudgetUsage])
def budget_usage(
    month: str | None = Query(default=None, description="YYYY-MM, defaults to current month"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return spend-vs-limit for every budget the user owns for a given calendar month."""
    today = date.today()
    if month:
        try:
            year, mon = int(month[:4]), int(month[5:7])
            month_start = date(year, mon, 1)
        except (ValueError, IndexError):
            raise HTTPException(400, "month must be YYYY-MM")
    else:
        month_start = today.replace(day=1)
        year, mon = month_start.year, month_start.month

    last_day = monthrange(year, mon)[1]
    month_end = date(year, mon, last_day)
    # Don't look into the future: cap the end date at today within the current month.
    if month_end > today:
        month_end = today

    budgets = db.scalars(
        select(models.Budget).where(models.Budget.owner_id == current_user.id)
        .order_by(models.Budget.category.nullsfirst(), models.Budget.id)
    ).all()

    result = []
    for b in budgets:
        conds = [
            models.Receipt.owner_id == current_user.id,
            models.Receipt.deleted_at.is_(None),
            models.Receipt.purchase_date >= month_start,
            models.Receipt.purchase_date <= month_end,
        ]
        if b.category is not None:
            conds.append(models.Receipt.category == b.category)
        spent = db.execute(
            select(func.coalesce(func.sum(models.Receipt.total), 0)).where(*conds)
        ).scalar_one()
        pct = float(spent / b.monthly_limit * 100) if b.monthly_limit else None
        result.append(schemas.BudgetUsage(
            budget=schemas.BudgetOut.model_validate(b),
            spent=spent,
            pct=pct,
        ))
    return result
