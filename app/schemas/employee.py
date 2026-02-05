"""
Employee Schemas
Pydantic models for employee data validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class EmployeeBase(BaseModel):
    """Base employee schema."""
    employee_code: Optional[str] = None
    name: str
    phone: Optional[str] = None
    salary: Optional[int] = None


class EmployeeCreate(EmployeeBase):
    """Schema for creating an employee."""
    row_number: int
    session_id: UUID


class EmployeeResponse(EmployeeBase):
    """Schema for employee response."""
    id: UUID
    session_id: UUID
    row_number: int
    salary_image_url: Optional[str] = None
    created_at: datetime
    formatted_salary: str
    latest_send_status: Optional[str] = None

    class Config:
        from_attributes = True


class EmployeeListResponse(BaseModel):
    """Schema for list of employees."""
    employees: List[EmployeeResponse]
    total: int
    session_id: Optional[UUID] = None
    filename: Optional[str] = None


class EmployeeUpdateRequest(BaseModel):
    """Schema for updating employee data."""
    employee_code: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    salary: Optional[int] = None
