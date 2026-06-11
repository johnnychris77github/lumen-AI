from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.deps import get_current_user, get_db
from app.db import models

router = APIRouter(tags=["inspections"])
ADM = {"admin", "super_admin", "security_admin"}


def val(x):
    return x.isoformat() if hasattr(x, "isoformat") else x


def out(r):
    return {c.name: val(getattr(r, c