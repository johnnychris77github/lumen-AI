from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.deps import get_current_user, get_db
from app.db import models

router = APIRouter(tags=["inspections"])
ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


def _n(v):
    return str(v).strip().lower() if v is not None and str(v).strip() else None


def _can_read(row, user):
    if _n(getattr(user, "role", None)) in ADMIN_ROLES:
        return True
    row