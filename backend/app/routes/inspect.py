from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.deps import get_db
from app.db import models

router = APIRouter(tags=["inspect"])


@router.post("/inspect")
async def inspect_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Stub inspection endpoint:

    - accepts an uploaded image
    - runs a *fake* model (hard-coded values for now)
    - writes a row into Postgres
    - returns the saved record
    """

    # Read the file to ensure it's actually uploaded (even though we don't use pixels yet)
    contents = await file.read()
    if not contents:
        # FastAPI will turn this into a 400
        raise ValueError("Empty file uploaded")

    # ---- STUB MODEL OUTPUT ----
    # You can plug real model predictions here later.
    stain_detected = True
    confidence = 0.92
    material_type = "unknown"  # e.g., "rigid_scope", "lumen", etc.
    status = "completed"

    row = models.Inspection(
        file_name=file.filename or "uploaded-image",
        stain_detected=stain_detected,
        confidence=confidence,
        material_type=material_type,
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "file_name": row.file_name,
        "stain_detected": row.stain_detected,
        "confidence": row.confidence,
        "material_type": row.material_type,
        "status": row.status,
    }
