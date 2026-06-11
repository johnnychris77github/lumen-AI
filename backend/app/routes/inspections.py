from fastapi import APIRouter, Depends, HTTPException
from app.deps import get_current_user, get_db
from app.db import models
router = APIRouter(tags=["inspections"])
@router.get("/inspections/{inspection_id}")
async def get_inspection(inspection_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    row = db.query