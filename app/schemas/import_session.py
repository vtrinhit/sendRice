"""
Import Session Schemas
Pydantic models for Excel import sessions.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ImportSessionCreate(BaseModel):
    """Schema for creating an import session."""
    filename: str
    sheet_name: str
    total_rows: int = 0


class ImportSessionResponse(BaseModel):
    """Schema for import session response."""
    id: UUID
    filename: str
    sheet_name: str
    imported_at: datetime
    total_rows: int
    status: str

    class Config:
        from_attributes = True


class ImportSessionListResponse(BaseModel):
    """Schema for list of import sessions."""
    sessions: list[ImportSessionResponse]
    total: int
