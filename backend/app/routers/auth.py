from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.models.user import User
from backend.app.schemas.auth import Token
from backend.app.services.security import verify_password, make_token
from backend.app.core.config import settings
import jwt
from jwt import InvalidTokenError

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return Token(access_token=make_token(user.username))

def get_current_user(request: Request) -> str:
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ",1)[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub") or "unknown"
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
