from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.deps import get_db
from app.db import models

import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

router = APIRouter(tags=["reports"])


@router.get("/reports/{inspection_id}.pdf")
def get_report(
    inspection_id: int,
    db: Session = Depends(get_db),
):
    """
    Generate a simple PDF report for a given inspection, backed by Postgres.
    """
    inspection = (
        db.query(models.Inspection)
        .filter(models.Inspection.id == inspection_id)
        .first()
    )

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    y = 800
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, f"LumenAI Inspection Report #{inspection.id}")
    y -= 40

    c.setFont("Helvetica", 11)
    lines = [
        f"Created at: {inspection.created_at}",
        f"File name: {inspection.file_name}",
        f"Stain detected: {inspection.stain_detected}",
        f"Confidence: {inspection.confidence:.2f}",
        f"Material type: {inspection.material_type}",
        f"Status: {inspection.status}",
    ]

    for line in lines:
        c.drawString(72, y, line)
        y -= 20

    c.showPage()
    c.save()
    buf.seek(0)

    headers = {
        "Content-Disposition": f'inline; filename="inspection-{inspection.id}.pdf"'
    }
    return StreamingResponse(buf, media_type="application/pdf", headers=headers)
