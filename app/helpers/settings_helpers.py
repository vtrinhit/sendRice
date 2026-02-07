"""
Settings Helpers
Centralized functions for retrieving application settings from the database.
"""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import AppSetting


async def get_image_config(db: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Retrieve image configuration from the database.

    Returns None if no config is saved (the service uses its own defaults).
    Returns the image config dict if settings exist.

    Args:
        db: Async database session

    Returns:
        Dictionary with image_start_col, image_end_col, image_start_row, image_end_row
        or None if no settings are configured.
    """
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "excel_config")
    )
    setting = result.scalar_one_or_none()

    if not setting or not setting.value:
        return None

    return {
        "salary_slip_sheet": setting.value.get("salary_slip_sheet", "Phiếu lương"),
        "image_start_col": setting.value.get("image_start_col", "B"),
        "image_end_col": setting.value.get("image_end_col", "H"),
        "image_start_row": setting.value.get("image_start_row", 4),
        "image_end_row": setting.value.get("image_end_row", 29),
    }


async def get_webhook_config(db: AsyncSession) -> Dict[str, Any]:
    """
    Retrieve webhook configuration from the database.

    Args:
        db: Async database session

    Returns:
        Dictionary with webhook_url, timeout, retry_count, message_content, send_delay
    """
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "webhook_config")
    )
    setting = result.scalar_one_or_none()

    if not setting or not setting.value:
        return {
            "webhook_url": "",
            "timeout": 30,
            "retry_count": 3,
            "message_content": "",
            "send_delay": 3
        }

    return {
        "webhook_url": setting.value.get("webhook_url", ""),
        "timeout": setting.value.get("timeout", 30),
        "retry_count": setting.value.get("retry_count", 3),
        "message_content": setting.value.get("message_content", ""),
        "send_delay": setting.value.get("send_delay", 3),
    }
