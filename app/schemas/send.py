"""
Send Schemas
Pydantic models for webhook send operations.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID


class SendRequest(BaseModel):
    """Schema for sending notification to single employee."""
    employee_id: UUID


class SendResponse(BaseModel):
    """Schema for send operation response."""
    employee_id: UUID
    status: str  # pending, sending, success, failed
    message: Optional[str] = None


class BatchSendRequest(BaseModel):
    """Schema for batch sending notifications."""
    employee_ids: List[str] = Field(..., min_length=1)


class BatchSendResponse(BaseModel):
    """Schema for batch send response."""
    total: int
    success: int
    failed: int
    results: List[SendResponse]


class WebhookPayload(BaseModel):
    """Schema for n8n webhook payload."""
    SDT: str = Field(..., description="Số điện thoại Zalo")
    Ten: str = Field(..., description="Tên nhân viên")
    Luong: int = Field(..., description="Số tiền lương")
    HinhAnhURL: str = Field(..., description="URL ảnh bảng lương trên Google Drive")


class WebhookResponse(BaseModel):
    """Schema for n8n webhook response."""
    status: str  # success, failed
    message: Optional[str] = None
