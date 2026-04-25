# Authentication module - stub implementation
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials

security = HTTPBearer()

async def get_current_user(credentials: Optional[HTTPAuthCredentials] = Depends(security)):
    """Retrieve current authenticated user from credentials."""
    if credentials:
        return {"token": credentials.credentials}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )
