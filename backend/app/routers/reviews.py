from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.app.db.session import SessionLocal
from backend.app.models.review import ReviewItem, ReviewFeedback
from backend.app.schemas.review import ReviewItemOut, FeedbackIn, ExportRow
from backend.app.routers.auth import get_current_user

router = APIRouter(prefix="/reviews", tags=["reviews"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.post("/seed", response_model=List[ReviewItemOut])
def seed(n: int = 5, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    base = "https://picsum.photos/seed"
    items = [ReviewItem(image_url=f"{base}/{i}/800/600", predicted_label=None, confidence=None) for i in range(n)]
    db.add_all(items); db.commit()
    for it in items: db.refresh(it)
    return items

@router.get("/queue", response_model=List[ReviewItemOut])
def queue(limit: int = 20, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    return db.query(ReviewItem).order_by(ReviewItem.id.desc()).limit(limit).all()

@router.post("/feedback")
def post_feedback(body: FeedbackIn, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    item = db.query(ReviewItem).get(body.item_id)
    if not item: raise HTTPException(status_code=404, detail="item not found")
    db.add(ReviewFeedback(item_id=item.id, true_label=body.true_label, reviewer=username)); db.commit()
    return {"ok": True}

@router.get("/export", response_model=List[ExportRow])
def export(db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    rows = (db.query(ReviewFeedback.true_label, ReviewItem.image_url)
              .join(ReviewItem, ReviewItem.id == ReviewFeedback.item_id)
              .all())
    return [ExportRow(image_url=u, label=lbl) for (lbl, u) in [(r[1], r[0]) for r in rows]]
