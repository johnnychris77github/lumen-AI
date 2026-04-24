from datetime import datetime, timedelta, timezone
from passlib.hash import pbkdf2_sha256 as pwdhash  # <-- use PBKDF2-SHA256
import jwt
from backend.app.core.config import settings

ALGO = "HS256"

def hash_password(p: str) -> str:
    return pwdhash.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwdhash.verify(p, hashed)

def make_token(sub: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": sub, "exp": exp}, settings.SECRET_KEY, algorithm=ALGO)
