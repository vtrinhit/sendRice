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
    image_start_row: Optional[int] = Field(default=None, description="Hàng bắt đầu cho ảnh lương")
    image_end_row: Optional[int] = Field(default=None, description="Hàng kết thúc cho ảnh lương")
    image_start_col: str = Field(default="A", description="Cột bắt đầu cho ảnh lương")
    image_end_col: str = Field(default="G", description="Cột kết thúc cho ảnh lương")


class WebhookConfigSchema(BaseModel):
    """Schema for n8n webhook configuration."""
    webhook_url: str = Field(..., description="URL webhook n8n")
    timeout: int = Field(default=30, description="Timeout (giây)", ge=5, le=120)
    retry_count: int = Field(default=3, description="Số lần thử lại", ge=0, le=5)


class GoogleDriveConfigSchema(BaseModel):
    """Schema for Google Drive configuration."""
    folder_id: Optional[str] = Field(default=None, description="ID thư mục Drive gốc")
    create_year_folders: bool = Field(default=True, description="Tạo thư mục theo năm")
    create_month_folders: bool = Field(default=True, description="Tạo thư mục theo tháng")


class AllSettingsResponse(BaseModel):
    """Schema for all settings response."""
    excel_config: ExcelConfigSchema
    webhook_config: Optional[WebhookConfigSchema] = None
    gdrive_config: Optional[GoogleDriveConfigSchema] = None
