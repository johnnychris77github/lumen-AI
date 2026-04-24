from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.models.user import User
from backend.app.services.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.post("/seed_admin")
def seed_admin(db: Session = Depends(get_db)):
    if not db.query(User).filter(User.username == "admin").first():
        db.add(User(username="admin", password_hash=hash_password("admin123"), is_admin=True))
        db.commit()
    return {"ok": True}
