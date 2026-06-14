from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from app.core import settings as settings_module
from app.core.jwt_auth import extract_actor_from_jwt


@pytest.fixture(autouse=True)
def reset_settings():
    original = settings_module.settings.model_copy()
    settings_module.settings.LUMENAI_OIDC_PROVIDER = "generic"
    settings_module.settings.LUMENAI_JWT_ACTOR_ID_CLAIM = ""
    settings_module.settings.LUMENAI_JWT_ACTOR_NAME_CLAIM = ""
    settings_module.settings.LUMENAI_JWT_ACTOR_EMAIL_CLAIM = ""
    settings_module.settings.LUMENAI_JWT_ROLE_CLAIM = ""
    settings_module.settings.LUMENAI_JWT_TENANT_ID_CLAIM = ""
    settings_module.settings.LUMENAI_JWT_TENANT_NAME_CLAIM = ""
    yield
    for name, value in original.model_dump().items():
        setattr(settings_module.settings, name, value)


def test_generic_profile_works():
    actor = extract_actor_from_jwt(
        {
            "sub": "actor-1",
            "name": "Generic User",
            "email": "generic@example.com",
            "roles": ["tenant_admin"],
            "tenant_id": "tenant-a",
            "tenant_name": "Tenant A",
        },
        settings_module.settings,
    )

    assert actor.actor_id == "actor-1"
    assert actor.actor_name == "Generic User"
    assert actor.actor_email == "generic@example.com"
    assert actor.actor_role == "tenant_admin"
    assert actor.tenant_id == "tenant-a"
    assert actor.tenant_name == "Tenant A"


def test_azure_ad_profile_extracts_tenant_and_role():
    settings_module.settings.LUMENAI_OIDC_PROVIDER = "azure_ad"

    actor = extract_actor_from_jwt(
        {
            "oid": "azure-object-id",
            "sub": "fallback-sub",
            "name": "Azure User",
            "preferred_username": "azure@example.com",
            "roles": ["security_admin"],
            "tid": "azure-tenant-id",
        },
        settings_module.settings,
    )

    assert actor.actor_id == "azure-object-id"
    assert actor.actor_email == "azure@example.com"
    assert actor.actor_role == "security_admin"
    assert actor.tenant_id == "azure-tenant-id"


def test_okta_profile_extracts_groups_role():
    settings_module.settings.LUMENAI_OIDC_PROVIDER = "okta"

    actor = extract_actor_from_jwt(
        {
            "sub": "okta-sub",
            "name": "Okta User",
            "email": "okta@example.com",
            "groups": ["spd_manager", "everyone"],
            "organization": {"name": "Okta Tenant"},
        },
        settings_module.settings,
    )

    assert actor.actor_id == "okta-sub"
    assert actor.actor_role == "spd_manager"
    assert actor.tenant_name == "Okta Tenant"


def test_auth0_profile_extracts_permissions_roles():
    settings_module.settings.LUMENAI_OIDC_PROVIDER = "auth0"

    actor = extract_actor_from_jwt(
        {
            "sub": "auth0|user",
            "name": "Auth0 User",
            "email": "auth0@example.com",
            "permissions": ["viewer", "read:audit"],
            "org_id": "org_123",
            "org_name": "Auth0 Org",
        },
        settings_module.settings,
    )

    assert actor.actor_id == "auth0|user"
    assert actor.actor_role == "viewer"
    assert actor.tenant_id == "org_123"
    assert actor.tenant_name == "Auth0 Org"


def test_custom_claim_settings_override_defaults():
    settings_module.settings.LUMENAI_OIDC_PROVIDER = "custom"
    settings_module.settings.LUMENAI_JWT_ACTOR_ID_CLAIM = "identity.id"
    settings_module.settings.LUMENAI_JWT_ACTOR_NAME_CLAIM = "identity.display_name"
    settings_module.settings.LUMENAI_JWT_ACTOR_EMAIL_CLAIM = "identity.mail"
    settings_module.settings.LUMENAI_JWT_ROLE_CLAIM = "access.roles"
    settings_module.settings.LUMENAI_JWT_TENANT_ID_CLAIM = "tenant.external_id"
    settings_module.settings.LUMENAI_JWT_TENANT_NAME_CLAIM = "tenant.display_name"

    actor = extract_actor_from_jwt(
        {
            "identity": {
                "id": "custom-id",
                "display_name": "Custom User",
                "mail": "custom@example.com",
            },
            "access": {"roles": ["tenant_admin"]},
            "tenant": {"external_id": "tenant-custom", "display_name": "Custom Tenant"},
        },
        settings_module.settings,
    )

    assert actor.actor_id == "custom-id"
    assert actor.actor_name == "Custom User"
    assert actor.actor_email == "custom@example.com"
    assert actor.actor_role == "tenant_admin"
    assert actor.tenant_id == "tenant-custom"
    assert actor.tenant_name == "Custom Tenant"


def test_missing_optional_claims_do_not_crash():
    actor = extract_actor_from_jwt({"sub": "minimal-user"}, settings_module.settings)

    assert actor.actor_id == "minimal-user"
    assert actor.actor_name == "minimal-user"
    assert actor.actor_email == ""
    assert actor.actor_role == "viewer"
    assert actor.tenant_id == ""
    assert actor.tenant_name == ""


def test_missing_required_subject_actor_id_fails_safely():
    with pytest.raises(HTTPException) as exc:
        extract_actor_from_jwt({"email": "missing-sub@example.com"}, settings_module.settings)

    assert exc.value.status_code == 401


def test_no_token_or_claim_secrets_are_leaked_in_errors():
    secret = "super-secret-claim-value"

    with pytest.raises(HTTPException) as exc:
        extract_actor_from_jwt({"email": secret}, settings_module.settings)

    assert secret not in str(exc.value.detail)
