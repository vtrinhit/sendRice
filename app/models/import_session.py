"""
Import Session Model
Tracks each Excel import session.
"""
from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from datetime import datetime
from typing import List
import uuid

from app.database import Base


class ImportSession(Base):
    """Tracks an Excel file import session."""

    __tablename__ = "import_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(100), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Relationships
    employees: Mapped[List["Employee"]] = relationship(
        "Employee",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ImportSession(filename={self.filename}, rows={self.total_rows})>"
