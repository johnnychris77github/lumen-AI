from fastapi import APIRouter

router = APIRouter()

@router.get("/api/reviews/queue")
async def reviews_queue():
    # Minimal stub: empty queue
    return {"items": []}
