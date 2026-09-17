import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import RefreshToken, User

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(db: Session, user_id: int, device_id: str | None = None) -> str:
    raw = uuid.uuid4().hex
    token = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.add(RefreshToken(user_id=user_id, token=token, device_id=device_id, expires_at=expires_at))
    db.commit()
    return token


def rotate_refresh_token(db: Session, raw_refresh: str) -> RefreshToken | None:
    token = hashlib.sha256(raw_refresh.encode()).hexdigest()
    record = db.query(RefreshToken).filter(RefreshToken.token == token).first()
    if not record or record.expires_at < datetime.now(timezone.utc):
        return None
    db.delete(record)
    db.commit()
    return record


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise credentials_exc
    return user


def device_fingerprint(parts: dict) -> str:
    raw = "|".join(f"{k}={v}" for k, v in sorted(parts.items()))
    return hashlib.sha256(raw.encode()).hexdigest()