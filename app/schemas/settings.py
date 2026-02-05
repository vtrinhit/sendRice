"""
Settings Schemas
Pydantic models for application settings.
"""
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class AppSettingBase(BaseModel):
    """Base settings schema."""
    key: str
    value: dict


class AppSettingCreate(AppSettingBase):
    """Schema for creating a setting."""
    pass


class AppSettingResponse(AppSettingBase):
    """Schema for setting response."""
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True


class ExcelConfigSchema(BaseModel):
    """Schema for Excel import configuration."""
    sheet_name: str = Field(default="Sheet1", description="Tên sheet chứa dữ liệu")
    header_row: int = Field(default=1, description="Hàng tiêu đề", ge=1)
    data_start_row: int = Field(default=2, description="Hàng bắt đầu dữ liệu", ge=1)
    code_column: str = Field(default="A", description="Cột mã nhân viên")
    name_column: str = Field(default="B", description="Cột tên nhân viên")
    phone_column: str = Field(default="C", description="Cột số điện thoại")
    salary_column: str = Field(default="D", description="Cột lương")
    # Image generation config
    image_start_row: int = Field(default=4, description="Hàng bắt đầu cho ảnh lương", ge=1)
    image_end_row: int = Field(default=29, description="Hàng kết thúc cho ảnh lương", ge=1)
    image_start_col: str = Field(default="B", description="Cột bắt đầu cho ảnh lương")
    image_end_col: str = Field(default="H", description="Cột kết thúc cho ảnh lương")


class WebhookConfigSchema(BaseModel):
    """Schema for n8n webhook configuration."""
    webhook_url: str = Field(..., description="URL webhook n8n")
    timeout: int = Field(default=30, description="Timeout (giây)", ge=5, le=120)
    retry_count: int = Field(default=3, description="Số lần thử lại", ge=0, le=5)


class AllSettingsResponse(BaseModel):
    """Schema for all settings response."""
    excel_config: ExcelConfigSchema
    webhook_config: Optional[WebhookConfigSchema] = None
