"""Receipt categories — anyone signed in can list them; admins manage them.

Receipts store the category name as a string (Receipt.category), so renaming
a category cascades to the receipts that reference it to keep grouping intact.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user, require_admin
from .. import models, schemas

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[schemas.CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.scalars(select(models.Category).order_by(models.Category.name)).all()


@router.post(
    "",
    response_model=schemas.CategoryOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_category(payload: schemas.CategoryCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Category name cannot be empty")
    if db.scalar(select(models.Category).where(models.Category.name == name)):
        raise HTTPException(409, "A category with that name already exists")

    category = models.Category(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch(
    "/{category_id}",
    response_model=schemas.CategoryOut,
    dependencies=[Depends(require_admin)],
)
def update_category(
    category_id: int,
    payload: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
):
    category = db.get(models.Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")

    new_name = payload.name.strip()
    if not new_name:
        raise HTTPException(422, "Category name cannot be empty")

    if new_name != category.name:
        clash = db.scalar(select(models.Category).where(models.Category.name == new_name))
        if clash:
            raise HTTPException(409, "A category with that name already exists")
        # Cascade the rename to receipts that use the old name.
        db.execute(
            update(models.Receipt)
            .where(models.Receipt.category == category.name)
            .values(category=new_name)
        )
        category.name = new_name
        db.commit()
        db.refresh(category)

    return category


@router.delete(
    "/{category_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.get(models.Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    # Receipts keep their stored category string (historical label); only the
    # managed option is removed so it no longer appears in the picker.
    db.delete(category)
    db.commit()
