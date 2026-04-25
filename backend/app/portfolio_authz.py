# Portfolio authorization - stub implementation
from app.auth import get_current_user

async def require_portfolio_access(current_user = Depends(get_current_user)):
    """Check if user has portfolio access."""
    if not current_user:
        raise Exception("User not authenticated")
    return current_user
