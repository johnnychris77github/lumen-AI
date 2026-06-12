from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(100), default="default-tenant", nullable=False, index=True)
    tenant_name: Mapped[str] = mapped_column(String(255), default="Default Tenant", nullable=False)
    actor_email: Mapped[str] = mapped_column(String(255), default="", nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    request_method: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    request_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    client_ip: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    details: Mapped[str] = mapped_column(String(4000), default="", nullable=False)
    compliance_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
