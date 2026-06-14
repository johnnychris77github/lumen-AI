from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.scim import (
    ScimSettings,
    create_or_update_user,
    deactivate_user,
    list_groups,
    list_users,
    patch_user,
    require_scim_auth,
    scim_user_response,
    upsert_group,
)
from app.deps import get_db

router = APIRouter(tags=["scim"])


def get_scim_settings(request: Request) -> ScimSettings:
    return require_scim_auth(request)


@router.get("/scim/v2/Users")
def get_users(db: Session = Depends(get_db), settings: ScimSettings = Depends(get_scim_settings)):
    return list_users(db, settings)


@router.get("/scim/v2/Users/{user_id}")
def get_user(user_id: str, db: Session = Depends(get_db), settings: ScimSettings = Depends(get_scim_settings)):
    from app.core.scim import get_user as load_user

    return scim_user_response(load_user(db, user_id, settings))


@router.post("/scim/v2/Users", status_code=status.HTTP_201_CREATED)
def post_user(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    settings: ScimSettings = Depends(get_scim_settings),
):
    return scim_user_response(create_or_update_user(db, payload, settings, request=request))


@router.patch("/scim/v2/Users/{user_id}")
def patch_scim_user(
    user_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    settings: ScimSettings = Depends(get_scim_settings),
):
    return scim_user_response(patch_user(db, user_id, payload, settings, request=request))


@router.delete("/scim/v2/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: ScimSettings = Depends(get_scim_settings),
):
    deactivate_user(db, user_id, settings, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/scim/v2/Groups")
def get_groups(db: Session = Depends(get_db), settings: ScimSettings = Depends(get_scim_settings)):
    return list_groups(db, settings)


@router.post("/scim/v2/Groups", status_code=status.HTTP_201_CREATED)
def post_group(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    settings: ScimSettings = Depends(get_scim_settings),
):
    return upsert_group(db, payload, settings, request=request)


@router.patch("/scim/v2/Groups/{group_id}")
def patch_group(
    group_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    settings: ScimSettings = Depends(get_scim_settings),
):
    return upsert_group(db, payload, settings, request=request, group_id=group_id)
