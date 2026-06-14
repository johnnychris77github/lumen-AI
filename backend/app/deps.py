from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.session_security import authenticate_request
from app.core.settings import settings
from app.db import SessionLocal
from app.db import models


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
):
    actor = authenticate_request(request, db, settings)

    if actor.token_type in {"dev_token", "api_token", "jwt"}:
        return actor

    if actor.token_type == "user_email":
        user = (
            db.query(models.User)
            .filter(models.User.email == actor.email)
            .first()
        )
        if user:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
    )
