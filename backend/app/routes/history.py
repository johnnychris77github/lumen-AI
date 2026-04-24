from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.db import models

router = APIRouter(tags=["history"])


@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Return inspection history from Postgres, newest first.
    """
    rows: List[models.Inspection] = (
        db.query(models.Inspection)
        .order_by(models.Inspection.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "file_name": r.file_name,
            "stain_detected": r.stain_detected,
            "confidence": r.confidence,
            "material_type": r.material_type,
            "status": r.status,
        }
        for r in rows
    ]

    return {"items": items}
