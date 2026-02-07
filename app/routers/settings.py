"""
Settings Router
Handles application configuration.
"""
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import logging

from app.database import get_db
from app.models import AppSetting, User
from app.dependencies.auth import get_current_active_user
from app.schemas.settings import (
    ExcelConfigSchema,
    WebhookConfigSchema,
)
from app.services.webhook_service import webhook_service
from app.config import settings

logger = logging.getLogger(__name__)


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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
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
        "retry_count": 3,
        "message_content": ""
    }

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "excel_config": excel_config,
            "webhook_config": webhook_config,
            "webhook_configured": webhook_service.is_configured(),
        }
    )


@router.get("/")
async def get_all_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all application settings."""
    excel_config = await get_setting(db, "excel_config") or {}
    webhook_config = await get_setting(db, "webhook_config")

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
    }


@router.post("/excel")
async def update_excel_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    sheet_name: str = Form("Sheet1"),
    header_row: int = Form(1),
    data_start_row: int = Form(2),
    code_column: str = Form("A"),
    name_column: str = Form("B"),
    phone_column: str = Form("C"),
    salary_column: str = Form("D"),
    salary_slip_sheet: str = Form("Phiếu lương"),
    image_start_col: str = Form("B"),
    image_end_col: str = Form("H"),
    image_start_row: int = Form(4),
    image_end_row: int = Form(29),
):
    """Update Excel import configuration."""
    config = ExcelConfigSchema(
        sheet_name=sheet_name,
        header_row=header_row,
        data_start_row=data_start_row,
        code_column=code_column,
        name_column=name_column,
        phone_column=phone_column,
        salary_column=salary_column,
        salary_slip_sheet=salary_slip_sheet,
        image_start_col=image_start_col,
        image_end_col=image_end_col,
        image_start_row=image_start_row,
        image_end_row=image_end_row,
    )
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    webhook_url: str = Form(""),
    timeout: int = Form(30),
    retry_count: int = Form(3),
    message_content: str = Form(""),
):
    """Update webhook configuration."""
    logger.info(f"Updating webhook config: url={webhook_url}, timeout={timeout}, retry={retry_count}")
    config = WebhookConfigSchema(
        webhook_url=webhook_url,
        timeout=timeout,
        retry_count=retry_count,
        message_content=message_content,
    )
    await set_setting(db, "webhook_config", config.model_dump())
    logger.info("Webhook config saved to database")

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Test webhook connectivity."""
    result = await webhook_service.test_webhook()
    return result
