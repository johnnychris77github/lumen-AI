from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.db import models

router = APIRouter(tags=["inspections"])

ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


def _normalize(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _can_read_inspection(row: models.Inspection, current_user) -> bool:
    user_role = _normalize(getattr(current_user, "role", None))
