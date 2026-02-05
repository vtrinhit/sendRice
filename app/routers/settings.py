"""
Settings Router
Handles application configuration.
"""
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import AppSetting
from app.schemas.settings import (
    ExcelConfigSchema,
    WebhookConfigSchema,
    GoogleDriveConfigSchema,
    AllSettingsResponse
)
from app.services.gdrive_service import gdrive_service
from app.services.webhook_service import webhook_service
from app.config import settings


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


async def get_setting(db: AsyncSession, key: str) -> Optional[dict]:
    """Get a setting by key."""
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def set_setting(db: AsyncSession, key: str, value: dict):
    """Set a setting value."""
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = value
    else:
        setting = AppSetting(key=key, value=value)
        db.add(setting)

    await db.commit()
    return setting


@router.get("/page", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Render the settings page."""
    # Get all settings
    excel_config = await get_setting(db, "excel_config") or {
        "sheet_name": settings.default_sheet_name,
        "header_row": settings.default_header_row,
        "data_start_row": settings.default_data_start_row,
        "code_column": settings.default_code_column,
        "name_column": settings.default_name_column,
        "phone_column": settings.default_phone_column,
        "salary_column": settings.default_salary_column,
    }

    webhook_config = await get_setting(db, "webhook_config") or {
        "webhook_url": settings.n8n_webhook_url or "",
        "timeout": 30,
        "retry_count": 3
    }

    gdrive_config = await get_setting(db, "gdrive_config") or {
        "folder_id": settings.google_drive_folder_id or "",
        "create_year_folders": True,
        "create_month_folders": True
    }

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "excel_config": excel_config,
            "webhook_config": webhook_config,
            "gdrive_config": gdrive_config,
            "gdrive_connected": gdrive_service.is_configured(),
            "webhook_configured": webhook_service.is_configured(),
        }
    )


@router.get("/")
async def get_all_settings(
    db: AsyncSession = Depends(get_db)
):
    """Get all application settings."""
    excel_config = await get_setting(db, "excel_config") or {}
    webhook_config = await get_setting(db, "webhook_config")
    gdrive_config = await get_setting(db, "gdrive_config")

    return {
        "excel_config": ExcelConfigSchema(**{
            "sheet_name": settings.default_sheet_name,
            "header_row": settings.default_header_row,
            "data_start_row": settings.default_data_start_row,
            "code_column": settings.default_code_column,
            "name_column": settings.default_name_column,
            "phone_column": settings.default_phone_column,
            "salary_column": settings.default_salary_column,
            **excel_config
        }),
        "webhook_config": WebhookConfigSchema(**webhook_config) if webhook_config else None,
        "gdrive_config": GoogleDriveConfigSchema(**gdrive_config) if gdrive_config else None,
    }


@router.post("/excel")
async def update_excel_config(
    config: ExcelConfigSchema,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Update Excel import configuration."""
    await set_setting(db, "excel_config", config.model_dump())

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/toast.html",
            {
                "request": request,
                "message": "Cấu hình Excel đã được lưu",
                "type": "success"
            }
        )

    return {"status": "success", "message": "Excel configuration updated"}


@router.post("/webhook")
async def update_webhook_config(
    config: WebhookConfigSchema,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Update webhook configuration."""
    await set_setting(db, "webhook_config", config.model_dump())

    # Update the service
    webhook_service.webhook_url = config.webhook_url
    webhook_service.timeout = config.timeout
    webhook_service.retry_count = config.retry_count

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/toast.html",
            {
                "request": request,
                "message": "Cấu hình Webhook đã được lưu",
                "type": "success"
            }
        )

    return {"status": "success", "message": "Webhook configuration updated"}


@router.post("/webhook/test")
async def test_webhook(
    db: AsyncSession = Depends(get_db)
):
    """Test webhook connectivity."""
    result = await webhook_service.test_webhook()
    return result


@router.post("/gdrive")
async def update_gdrive_config(
    config: GoogleDriveConfigSchema,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Update Google Drive configuration."""
    await set_setting(db, "gdrive_config", config.model_dump())

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/toast.html",
            {
                "request": request,
                "message": "Cấu hình Google Drive đã được lưu",
                "type": "success"
            }
        )

    return {"status": "success", "message": "Google Drive configuration updated"}


@router.get("/gdrive/status")
async def gdrive_status():
    """Check Google Drive connection status."""
    return {
        "configured": gdrive_service.is_configured(),
        "folder_id": settings.google_drive_folder_id
    }


@router.get("/gdrive/files")
async def list_gdrive_files():
    """List files in the configured Google Drive folder."""
    if not gdrive_service.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Google Drive not configured"
        )

    files = gdrive_service.list_files()
    return {"files": files}
