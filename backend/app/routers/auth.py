import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import (
    verify_password,
    create_access_token,
    get_current_user,
    hash_password,
)
from ..email import send_email, email_configured, email_html
from ..config import settings
from .. import models, schemas, audit

router = APIRouter(prefix="/api/auth", tags=["auth"])

_RESET_TTL = timedelta(hours=1)
_VERIFY_TTL = timedelta(hours=24)


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def _make_token() -> tuple[str, str]:
    plain = secrets.token_urlsafe(32)
    return plain, _hash_token(plain)


@router.post("/login")
def login(
    username: str = Form(),
    password: str = Form(),
    totp_code: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """Authenticate with email + password.

    If 2FA is enabled and ``totp_code`` is omitted, returns 403 with
    ``detail: "mfa_required"`` so the client shows the TOTP prompt.
    """
    user = db.scalar(select(models.User).where(models.User.email == username))
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    if user.totp_enabled:
        if not totp_code:
            raise HTTPException(status_code=403, detail="mfa_required")
        if not pyotp.TOTP(user.totp_secret).verify(totp_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid authenticator code")

    audit.record(db, user, "auth.login")
    db.commit()
    return schemas.Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", status_code=204)
def change_password(
    payload: schemas.PasswordChange,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(payload.new_password)
    audit.record(db, current_user, "auth.password_change")
    db.commit()


@router.patch("/profile", response_model=schemas.UserOut)
def update_profile(
    payload: schemas.ProfileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name or None
    if payload.avatar_url is not None:
        current_user.avatar_url = payload.avatar_url or None
    db.commit()
    db.refresh(current_user)
    return current_user


# ── Password reset ────────────────────────────────────────────────────────────

@router.post("/forgot-password", status_code=204)
def forgot_password(payload: schemas.ForgotPassword, db: Session = Depends(get_db)):
    """Always returns 204 to avoid leaking which email addresses are registered."""
    user = db.scalar(select(models.User).where(models.User.email == payload.email))
    if not user or not user.is_active:
        return

    plain, hashed = _make_token()
    user.reset_token = hashed
    user.reset_token_expires = datetime.now(timezone.utc) + _RESET_TTL
    db.commit()

    if email_configured():
        link = f"{settings.app_base_url}/reset-password?token={plain}"
        name = user.full_name or user.email
        html = email_html(
            heading="Reset your password",
            body_lines=[
                f"Hi {name},",
                "We received a request to reset your Receipt Scanner password. "
                "Click the button below — the link expires in <strong>1 hour</strong>.",
            ],
            cta_label="Reset password",
            cta_url=link,
            footer_note="If you didn't request a password reset, you can safely ignore this email. "
                        "Your password won't change.",
        )
        try:
            send_email(user.email, "Reset your Receipt Scanner password", html)
        except Exception:
            pass


@router.post("/reset-password", status_code=204)
def reset_password(payload: schemas.ResetPassword, db: Session = Depends(get_db)):
    hashed = _hash_token(payload.token)
    user = db.scalar(
        select(models.User).where(
            models.User.reset_token == hashed,
            models.User.reset_token_expires > datetime.now(timezone.utc),
        )
    )
    if not user:
        raise HTTPException(400, "Reset link is invalid or has expired")
    user.hashed_password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    audit.record(db, user, "auth.password_reset")
    db.commit()


# ── Email verification ────────────────────────────────────────────────────────

@router.post("/send-verification", status_code=204)
def send_verification(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_verified:
        raise HTTPException(400, "Email is already verified")
    plain, hashed = _make_token()
    current_user.verification_token = hashed
    current_user.verification_token_expires = datetime.now(timezone.utc) + _VERIFY_TTL
    db.commit()
    if email_configured():
        link = f"{settings.app_base_url}/verify-email?token={plain}"
        name = current_user.full_name or current_user.email
        html = email_html(
            heading="Verify your email address",
            body_lines=[
                f"Hi {name},",
                "Click the button below to verify your email address and complete your "
                "Receipt Scanner account setup. The link expires in <strong>24 hours</strong>.",
            ],
            cta_label="Verify email address",
            cta_url=link,
            footer_note="If you didn't create a Receipt Scanner account, you can safely ignore this email.",
        )
        try:
            send_email(current_user.email, "Verify your Receipt Scanner email address", html)
        except Exception:
            pass


@router.post("/verify-email", status_code=204)
def verify_email(token: str, db: Session = Depends(get_db)):
    hashed = _hash_token(token)
    user = db.scalar(
        select(models.User).where(
            models.User.verification_token == hashed,
            models.User.verification_token_expires > datetime.now(timezone.utc),
        )
    )
    if not user:
        raise HTTPException(400, "Verification link is invalid or has expired")
    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    audit.record(db, user, "auth.email_verified")
    db.commit()
