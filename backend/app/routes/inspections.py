from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["inspections"])

@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: int):
    raise HTTPException(403, "Access denied")
