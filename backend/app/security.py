"""Password hashing, JWT creation, and auth dependencies."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from . import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise cred_exc
    except jwt.PyJWTError:
        raise cred_exc

    user = db.get(models.User, int(sub))
    if user is None or not user.is_active:
        raise cred_exc
    return user


def require_superadmin(
    user: models.User = Depends(get_current_user),
) -> models.User:
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Requires super-admin privileges")
    return user


def require_admin(
    user: models.User = Depends(get_current_user),
) -> models.User:
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Requires admin privileges")
    return user
