"""
Employee Model
Stores employee data extracted from Excel files.
"""
from sqlalchemy import Column, String, Integer, BigInteger, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from datetime import datetime
from typing import List, TYPE_CHECKING
import uuid

from app.database import Base

if TYPE_CHECKING:
    from app.models.import_session import ImportSession
    from app.models.send_history import SendHistory


class Employee(Base):
    """Employee data from an imported Excel file."""

    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("import_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    salary: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    salary_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Image generation status: pending, processing, completed, failed
    image_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending"
    )
    image_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    session: Mapped["ImportSession"] = relationship(
        "ImportSession",
        back_populates="employees"
    )
    send_history: Mapped[List["SendHistory"]] = relationship(
        "SendHistory",
        back_populates="employee",
        cascade="all, delete-orphan"
    )

    @property
    def formatted_salary(self) -> str:
        """Format salary as Vietnamese currency."""
        if self.salary is None:
            return "N/A"
        return f"{self.salary:,.0f}".replace(",", ".") + " VND"

    @property
    def latest_send_status(self) -> str | None:
        """Get the latest send status."""
        if not self.send_history:
            return None
        latest = max(self.send_history, key=lambda h: h.sent_at)
        return latest.status

    def __repr__(self) -> str:
        return f"<Employee(name={self.name}, phone={self.phone})>"
