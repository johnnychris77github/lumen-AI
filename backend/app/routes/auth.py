from fastapi import APIRouter, Form
from pydantic import BaseModel

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/api/auth/login", response_model=Token)
async def login(
    username: str = Form(...),
    password: str = Form(...),
    grant_type: str = Form(default="password"),
):
    # Minimal stub: ignore credentials and always return a dev token.
    # You can later wire this into the real users table.
    return Token(access_token="dev-token")
