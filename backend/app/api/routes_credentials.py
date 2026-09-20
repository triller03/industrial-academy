from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.core.licensing import public_origin
from app.core.security import get_current_user
from app.database import get_db
from app.models import Certificate, PortfolioEntry, User
from app.plans import can_public_portfolio
from app.schemas import CertificateOut, PortfolioOut, PortfolioPublishIn

router = APIRouter(prefix="/credentials", tags=["credentials"])


def _portfolio_out(entry: PortfolioEntry) -> PortfolioOut:
    origin = public_origin()
    return PortfolioOut(
        id=entry.id,
        project_id=entry.project_id,
        entry_ref=entry.entry_ref,
        title=entry.title,
        summary=entry.summary,
        published=entry.published,
        published_at=entry.published_at,
        public_url=f"{origin}/portfolio/{entry.entry_ref}" if entry.published and origin else "",
    )


@router.get("/certificates", response_model=list[CertificateOut])
def my_certificates(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = db.query(Certificate).filter(Certificate.user_id == current.id).all()
    return [CertificateOut.model_validate(r) for r in rows]


@router.get("/portfolio", response_model=list[PortfolioOut])
def my_portfolio(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = db.query(PortfolioEntry).filter(PortfolioEntry.user_id == current.id).all()
    return [_portfolio_out(r) for r in rows]


@router.post("/portfolio/{entry_id}/publish", response_model=PortfolioOut)
def publish_portfolio(
    entry_id: int,
    body: PortfolioPublishIn | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Professional+: publish a portfolio entry to a public URL."""
    if not can_public_portfolio(current):
        raise HTTPException(
            status_code=403,
            detail="The public portfolio is a Professional feature. Upgrade to share a verifiable work sample.",
        )
    entry = (
        db.query(PortfolioEntry)
        .filter(
            PortfolioEntry.id == entry_id,
            PortfolioEntry.user_id == current.id,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Portfolio entry not found")
    if body is not None and body.title:
        entry.title = body.title.strip()
    entry.published = True
    entry.published_at = datetime.now(timezone.utc)
    db.add(entry)
    log_activity(db, current.id, "portfolio.publish", entity=f"portfolio:{entry.id}",
                 detail={"entry_ref": entry.entry_ref})
    db.commit()
    db.refresh(entry)
    return _portfolio_out(entry)


@router.post("/portfolio/{entry_id}/unpublish", response_model=PortfolioOut)
def unpublish_portfolio(
    entry_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    entry = (
        db.query(PortfolioEntry)
        .filter(
            PortfolioEntry.id == entry_id,
            PortfolioEntry.user_id == current.id,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Portfolio entry not found")
    entry.published = False
    entry.published_at = None
    log_activity(db, current.id, "portfolio.unpublish", entity=f"portfolio:{entry.id}",
                 detail={"entry_ref": entry.entry_ref})
    db.commit()
    db.refresh(entry)
    return _portfolio_out(entry)


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