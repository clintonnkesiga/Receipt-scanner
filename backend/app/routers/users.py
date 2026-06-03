"""User management — super-admin only."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_superadmin, hash_password
from .. import models, schemas

# Every endpoint here requires a super-admin token.
router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_superadmin)],
)

VALID_ROLES = {"superadmin", "admin", "user"}


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(models.User).order_by(models.User.created_at)).all()


@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if payload.role not in VALID_ROLES:
        raise HTTPException(422, f"Invalid role; must be one of {sorted(VALID_ROLES)}")
    if db.scalar(select(models.User).where(models.User.email == payload.email)):
        raise HTTPException(409, "A user with that email already exists")

    user = models.User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current: models.User = Depends(require_superadmin),
):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")

    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(422, f"Invalid role; must be one of {sorted(VALID_ROLES)}")
        # Don't let a super-admin demote themselves out of access.
        if user.id == current.id and payload.role != "superadmin":
            raise HTTPException(400, "You cannot change your own role")
        user.role = payload.role

    if payload.full_name is not None:
        user.full_name = payload.full_name

    if payload.is_active is not None:
        if user.id == current.id and payload.is_active is False:
            raise HTTPException(400, "You cannot disable your own account")
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(require_superadmin),
):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == current.id:
        raise HTTPException(400, "You cannot delete your own account")

    db.delete(user)
    db.commit()
