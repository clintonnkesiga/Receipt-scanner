"""TOTP two-factor authentication endpoints."""
import base64
import io

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user
from .. import models, schemas, audit

router = APIRouter(prefix="/api/2fa", tags=["2fa"])


def _qr_data_uri(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


@router.get("/setup", response_model=schemas.TwoFASetupOut)
def setup_totp(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate (or return the existing pending) TOTP secret + QR code.

    Does NOT enable 2FA yet — call POST /enable with a valid code to confirm.
    Calling setup again while 2FA is already active resets the pending secret
    (the user would need to re-enable).
    """
    if not current_user.totp_secret or current_user.totp_enabled:
        current_user.totp_secret = pyotp.random_base32()
        current_user.totp_enabled = False
        db.commit()
        db.refresh(current_user)

    provisioning_uri = pyotp.TOTP(current_user.totp_secret).provisioning_uri(
        name=current_user.email, issuer_name="Receipt Scanner"
    )
    return schemas.TwoFASetupOut(
        secret=current_user.totp_secret,
        provisioning_uri=provisioning_uri,
        qr_data_uri=_qr_data_uri(provisioning_uri),
    )


@router.post("/enable", status_code=204)
def enable_totp(
    payload: schemas.TwoFACode,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify a TOTP code from the authenticator app and enable 2FA."""
    if current_user.totp_enabled:
        raise HTTPException(400, "2FA is already enabled")
    if not current_user.totp_secret:
        raise HTTPException(400, "Call GET /api/2fa/setup first to generate a secret")
    if not pyotp.TOTP(current_user.totp_secret).verify(payload.code, valid_window=1):
        raise HTTPException(400, "Invalid authenticator code — try again")
    current_user.totp_enabled = True
    audit.record(db, current_user, "auth.2fa_enabled")
    db.commit()


@router.post("/disable", status_code=204)
def disable_totp(
    payload: schemas.TwoFACode,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify a TOTP code and disable 2FA."""
    if not current_user.totp_enabled:
        raise HTTPException(400, "2FA is not enabled")
    if not pyotp.TOTP(current_user.totp_secret).verify(payload.code, valid_window=1):
        raise HTTPException(400, "Invalid authenticator code — try again")
    current_user.totp_enabled = False
    current_user.totp_secret = None
    audit.record(db, current_user, "auth.2fa_disabled")
    db.commit()
