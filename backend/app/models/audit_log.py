from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(100), default="default-tenant", nullable=False, index=True)
    tenant_name: Mapped[str] = mapped_column(String(255), default="Default Tenant", nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), default="", nullable=False, index=True)
    actor_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    actor_email: Mapped[str] = mapped_column(String(255), default="", nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    action: Mapped[str] = mapped_column(String(100), default="", nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    timestamp_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    request_source: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    metadata_json: Mapped[str] = mapped_column(String(4000), default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    request_method: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    request_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    client_ip: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    details: Mapped[str] = mapped_column(String(4000), default="", nullable=False)
    compliance_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def _prevent_audit_mutation(*_args, **_kwargs) -> None:
    raise ValueError("AuditLog records are immutable and append-only.")


event.listen(AuditLog, "before_update", _prevent_audit_mutation)
event.listen(AuditLog, "before_delete", _prevent_audit_mutation)
