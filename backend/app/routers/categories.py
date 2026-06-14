"""Receipt categories, scoped per user.

Every user sees the shared/system defaults (owner_id IS NULL) plus their own
categories, and manages only their own. Admins additionally manage the shared
defaults. Receipts store the category name as a string (Receipt.category), so
renaming a category cascades to the receipts that reference it — scoped to the
category's owner (or all receipts for a shared default).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/categories", tags=["categories"])

ELEVATED_ROLES = {"admin", "superadmin"}


def _is_admin(user: models.User) -> bool:
    return user.role in ELEVATED_ROLES


def _visible_to(user: models.User):
    """Filter: shared defaults plus the user's own categories."""
    return or_(models.Category.owner_id.is_(None), models.Category.owner_id == user.id)


def _load_visible(category_id: int, db: Session, user: models.User) -> models.Category:
    """Fetch a category the user may see, else 404 (don't leak other users')."""
    category = db.get(models.Category, category_id)
    if category is None or (
        category.owner_id is not None and category.owner_id != user.id
    ):
        raise HTTPException(404, "Category not found")
    return category


def _require_editable(category: models.Category, user: models.User) -> None:
    """Own categories are editable by the owner; shared defaults by admins only."""
    if category.owner_id == user.id:
        return
    if category.owner_id is None and _is_admin(user):
        return
    raise HTTPException(403, "You can only manage your own categories")


@router.get("", response_model=list[schemas.CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.scalars(
        select(models.Category)
        .where(_visible_to(current_user))
        .order_by(models.Category.name)
    ).all()


@router.post("", response_model=schemas.CategoryOut, status_code=201)
def create_category(
    payload: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Category name cannot be empty")
    # Reject names that already exist in the user's visible set (shared or own).
    clash = db.scalar(
        select(models.Category).where(
            models.Category.name == name, _visible_to(current_user)
        )
    )
    if clash:
        raise HTTPException(409, "A category with that name already exists")

    category = models.Category(name=name, owner_id=current_user.id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    category_id: int,
    payload: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    category = _load_visible(category_id, db, current_user)
    _require_editable(category, current_user)

    new_name = payload.name.strip()
    if not new_name:
        raise HTTPException(422, "Category name cannot be empty")

    if new_name != category.name:
        clash = db.scalar(
            select(models.Category).where(
                models.Category.name == new_name,
                _visible_to(current_user),
                models.Category.id != category.id,
            )
        )
        if clash:
            raise HTTPException(409, "A category with that name already exists")

        # Cascade the rename. A shared default touches every receipt that uses
        # the name; an owned category only that owner's receipts.
        cascade = update(models.Receipt).where(models.Receipt.category == category.name)
        if category.owner_id is not None:
            cascade = cascade.where(models.Receipt.owner_id == category.owner_id)
        db.execute(cascade.values(category=new_name))

        category.name = new_name
        db.commit()
        db.refresh(category)

    return category


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    category = _load_visible(category_id, db, current_user)
    _require_editable(category, current_user)
    # Receipts keep their stored category string (historical label); only the
    # managed option is removed so it no longer appears in the picker.
    db.delete(category)
    db.commit()
