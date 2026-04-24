from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    """
    Simple healthcheck for edge / k8s / docker.
    """
    return {"status": "ok"}


@router.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Stub login that always returns a dev token.

    Frontend (and curl) expect /api/auth/login to exist and return
    an access_token + token_type.
    """
    # You *could* validate form_data.username/password here later.
    return {
        "access_token": "dev-token",
        "token_type": "bearer",
    }


@router.get("/reviews/queue")
async def reviews_queue():
    """
    Stubbed queue endpoint for pending inspections.

    Later we can wire this into the inspections table (or a dedicated
    review queue table). For now it just returns an empty list.
    """
    return {"items": []}
