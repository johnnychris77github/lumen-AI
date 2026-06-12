from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditChainAnchor(Base):
    __tablename__ = "audit_chain_anchors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    anchor_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    last_audit_log_id: Mapped[int] = mapped_column(Integer, nullable=False)
    records_covered: Mapped[int] = mapped_column(Integer, nullable=False)
    anchor_provider: Mapped[str] = mapped_column(String(100), default="internal", nullable=False)
    anchor_reference: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
