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
        "image_start_col": setting.value.get("image_start_col", "B"),
        "image_end_col": setting.value.get("image_end_col", "H"),
        "image_start_row": setting.value.get("image_start_row", 4),
        "image_end_row": setting.value.get("image_end_row", 29),
    }
