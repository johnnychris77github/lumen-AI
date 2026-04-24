from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, func

from app.db.session import Base


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    file_name = Column(String(512), nullable=False)
    stain_detected = Column(Boolean, nullable=False)
    confidence = Column(Float, nullable=False)
    material_type = Column(String(128), nullable=False)

    # Optional, but useful for UI
    status = Column(String(32), nullable=False, server_default="completed")
