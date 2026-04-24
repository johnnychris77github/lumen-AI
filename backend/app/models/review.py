from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Float, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base

class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_url: Mapped[str] = mapped_column(Text)
    predicted_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    feedbacks: Mapped[List["ReviewFeedback"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan"
    )

class ReviewFeedback(Base):
    __tablename__ = "review_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("review_items.id", ondelete="CASCADE"), index=True)
    true_label: Mapped[str] = mapped_column(String(64))
    reviewer: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["ReviewItem"] = relationship(back_populates="feedbacks")
