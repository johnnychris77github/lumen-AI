from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

UNSAFE_SECRET_VALUES = {
    "",
    "changeme",
    "change-me",
    "dev-token",
    "dev-secret",
    "devsecret",
    "local-only",
    "local-only-default",
    "password",
    "secret",
}


class SecretValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SecretIssue:
    name: str
    reason: str


def mask_secret(value: str | None) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 8:
        return f"{value[:1]}***{value[-1:]}"
    return f"{value[:2]}***{value[-2:]}"


def is_unsafe_secret(value: str | None) -> bool:
    normalized = str(value or "").strip()
    lowered = normalized.lower()
    if lowered in UNSAFE_SECRET_VALUES:
        return True
    if len(normalized) < 16:
        return True
    return False


def _setting_value(settings: Any, name: str) -> str:
    value = getattr(settings, name, None)
    if value is None:
        value = os.getenv(name, "")
    return str(value or "").strip()


def _environment(settings: Any) -> str:
    return (_setting_value(settings, "LUMENAI_ENV") or "development").lower()


def _storage_is_non_local() -> bool:
    endpoint = os.getenv("S3_ENDPOINT", "").strip().lower()
    if not endpoint:
        return False
    return not any(marker in endpoint for marker in ("localhost", "127.0.0.1", "minio"))


def _add_missing_or_unsafe(issues: list[SecretIssue], name: str, value: str | None) -> None:
    if not str(value or "").strip():
        issues.append(SecretIssue(name, "missing"))
    elif is_unsafe_secret(value):
        issues.append(SecretIssue(name, "unsafe"))


def validate_required_secrets(settings: Any) -> None:
    if _environment(settings) != "production":
        return

    issues: list[SecretIssue] = []
    _add_missing_or_unsafe(issues, "SECRET_KEY", _setting_value(settings, "SECRET_KEY"))
    _add_missing_or_unsafe(issues, "DATABASE_URL", _setting_value(settings, "DATABASE_URL"))

    jwt_secret = _setting_value(settings, "JWT_SECRET_KEY") or _setting_value(settings, "LUMENAI_JWT_SECRET")
    _add_missing_or_unsafe(issues, "JWT_SECRET_KEY", jwt_secret)

    evidence_signing_enabled = os.getenv("LUMENAI_EVIDENCE_SIGNING_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if evidence_signing_enabled or os.getenv("LUMENAI_EVIDENCE_SIGNING_SECRET") is not None:
        _add_missing_or_unsafe(
            issues,
            "LUMENAI_EVIDENCE_SIGNING_SECRET",
            os.getenv("LUMENAI_EVIDENCE_SIGNING_SECRET", ""),
        )

    if _storage_is_non_local():
        for name in ("S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_BUCKET"):
            _add_missing_or_unsafe(issues, name, os.getenv(name, ""))

    if issues:
        names = ", ".join(f"{issue.name} ({issue.reason})" for issue in issues)
        raise SecretValidationError(f"Production secret validation failed: {names}")
