"""
Send History Model
Tracks webhook send attempts and their results.
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class SendHistory(Base):
    """History of Zalo notification send attempts."""

    __tablename__ = "send_history"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending"
    )  # pending, sending, success, failed
    webhook_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee",
        back_populates="send_history"
    )

    def __repr__(self) -> str:
        return f"<SendHistory(employee_id={self.employee_id}, status={self.status})>"
