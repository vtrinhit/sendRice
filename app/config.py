"""
Application Configuration
Uses Pydantic Settings for environment variable management.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(
        default="postgresql://sendrice:sendrice@localhost:5432/sendrice",
        alias="DATABASE_URL"
    )

    # Security
    secret_key: str = Field(
        default="development-secret-key-change-in-production",
        alias="SECRET_KEY"
    )

    # n8n Webhook
    n8n_webhook_url: Optional[str] = Field(
        default=None,
        alias="N8N_WEBHOOK_URL"
    )

    # CORS
    allowed_origins: str = Field(
        default="http://localhost:8000",
        alias="ALLOWED_ORIGINS"
    )

    # File paths
    upload_dir: str = "uploads"
    temp_images_dir: str = "temp_images"

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Excel defaults
    default_sheet_name: str = "Danh sách NV"
    default_name_column: str = "B"
    default_phone_column: str = "C"
    default_salary_column: str = "D"
    default_code_column: str = "A"
    default_header_row: int = 1
    default_data_start_row: int = 2

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse allowed origins into a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


# Global settings instance
settings = Settings()

# Ensure directories exist
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.temp_images_dir, exist_ok=True)
