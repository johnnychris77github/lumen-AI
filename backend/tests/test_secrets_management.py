from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.secrets import (
    SecretValidationError,
    is_unsafe_secret,
    mask_secret,
    validate_required_secrets,
)


def settings(**overrides):
    defaults = {
        "LUMENAI_ENV": "development",
        "SECRET_KEY": "",
        "JWT_SECRET_KEY": "",
        "DATABASE_URL": "",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def clear_secret_env(monkeypatch):
    for name in (
        "LUMENAI_EVIDENCE_SIGNING_ENABLED",
        "LUMENAI_EVIDENCE_SIGNING_SECRET",
        "S3_ENDPOINT",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
        "S3_BUCKET",
        "JWT_SECRET_KEY",
        "LUMENAI_JWT_SECRET",
        "SECRET_KEY",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_development_mode_allows_safe_local_defaults(monkeypatch):
    clear_secret_env(monkeypatch)

    validate_required_secrets(settings(LUMENAI_ENV="development"))
    validate_required_secrets(settings(LUMENAI_ENV="test"))


def test_production_mode_fails_when_required_secrets_missing(monkeypatch):
    clear_secret_env(monkeypatch)

    with pytest.raises(SecretValidationError) as exc:
        validate_required_secrets(settings(LUMENAI_ENV="production"))

    message = str(exc.value)
    assert "SECRET_KEY" in message
    assert "JWT_SECRET_KEY" in message
    assert "DATABASE_URL" in message


def test_production_mode_fails_when_unsafe_defaults_are_used(monkeypatch):
    clear_secret_env(monkeypatch)

    with pytest.raises(SecretValidationError) as exc:
        validate_required_secrets(
            settings(
                LUMENAI_ENV="production",
                SECRET_KEY="changeme",
                JWT_SECRET_KEY="secret",
                DATABASE_URL="password",
            )
        )

    message = str(exc.value)
    assert "SECRET_KEY (unsafe)" in message
    assert "JWT_SECRET_KEY (unsafe)" in message
    assert "DATABASE_URL (unsafe)" in message


def test_production_mode_passes_when_strong_values_are_provided(monkeypatch):
    clear_secret_env(monkeypatch)
    monkeypatch.setenv("LUMENAI_EVIDENCE_SIGNING_ENABLED", "true")
    monkeypatch.setenv("LUMENAI_EVIDENCE_SIGNING_SECRET", "evidence-signing-secret-value-12345")

    validate_required_secrets(
        settings(
            LUMENAI_ENV="production",
            SECRET_KEY="application-secret-value-12345",
            JWT_SECRET_KEY="jwt-secret-value-67890",
            DATABASE_URL="postgresql+psycopg2://lumen:strong-password@db:5432/lumenai",
        )
    )


def test_mask_secret_does_not_expose_full_secret_values():
    secret = "super-sensitive-secret-value"
    masked = mask_secret(secret)

    assert masked != secret
    assert "sensitive" not in masked
    assert masked.startswith("su")
    assert masked.endswith("ue")


def test_error_messages_do_not_leak_secret_values(monkeypatch):
    clear_secret_env(monkeypatch)
    unsafe_value = "super-short"

    with pytest.raises(SecretValidationError) as exc:
        validate_required_secrets(
            settings(
                LUMENAI_ENV="production",
                SECRET_KEY=unsafe_value,
                JWT_SECRET_KEY="jwt-secret-value-67890",
                DATABASE_URL="postgresql+psycopg2://lumen:strong-password@db:5432/lumenai",
            )
        )

    assert unsafe_value not in str(exc.value)


def test_is_unsafe_secret_blocks_empty_short_and_known_defaults():
    assert is_unsafe_secret("")
    assert is_unsafe_secret("dev-token")
    assert is_unsafe_secret("secret")
    assert is_unsafe_secret("short")
    assert not is_unsafe_secret("long-random-secret-value-12345")
