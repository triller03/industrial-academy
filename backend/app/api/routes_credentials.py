from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import Certificate, PortfolioEntry, User
from app.schemas import CertificateOut, PortfolioOut

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.get("/certificates", response_model=list[CertificateOut])
def my_certificates(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = db.query(Certificate).filter(Certificate.user_id == current.id).all()
    return [CertificateOut.model_validate(r) for r in rows]


@router.get("/portfolio", response_model=list[PortfolioOut])
def my_portfolio(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = db.query(PortfolioEntry).filter(PortfolioEntry.user_id == current.id).all()
    return [PortfolioOut.model_validate(r) for r in rows]


@router.get("/certificates/verify/{token}")
def verify_certificate(token: str, db: Session = Depends(get_db)):
    cert = db.query(Certificate).filter(Certificate.verification_token == token).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    user = db.query(User).filter(User.id == cert.user_id).first()
    return {
        "certificate_ref": cert.certificate_ref,
        "issued_to": user.email if user else "unknown",
        "score": cert.score,
        "issued_at": cert.issued_at,
        "valid": True,
    }