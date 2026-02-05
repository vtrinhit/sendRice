#!/usr/bin/env python3
"""
Database Initialization Script
Creates tables and seeds initial data.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine, Base, async_session_maker
from app.models import AppSetting, ImportSession, Employee, SendHistory
from app.config import settings


async def init_database():
    """Initialize the database with tables and default settings."""
    print("=" * 50)
    print("SendRice Database Initialization")
    print("=" * 50)

    # Create all tables
    print("\n[1/3] Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("      Tables created successfully!")

    # Seed default settings
    print("\n[2/3] Seeding default settings...")
    async with async_session_maker() as session:
        # Check if settings already exist
        result = await session.execute(
            text("SELECT COUNT(*) FROM app_settings")
        )
        count = result.scalar()

        if count == 0:
            # Add default Excel config
            excel_config = AppSetting(
                key="excel_config",
                value={
                    "sheet_name": settings.default_sheet_name,
                    "header_row": settings.default_header_row,
                    "data_start_row": settings.default_data_start_row,
                    "code_column": settings.default_code_column,
                    "name_column": settings.default_name_column,
                    "phone_column": settings.default_phone_column,
                    "salary_column": settings.default_salary_column,
                    "image_start_col": "A",
                    "image_end_col": "G",
                }
            )
            session.add(excel_config)

            # Add default webhook config
            webhook_config = AppSetting(
                key="webhook_config",
                value={
                    "webhook_url": settings.n8n_webhook_url or "",
                    "timeout": 30,
                    "retry_count": 3,
                }
            )
            session.add(webhook_config)

            # Add default Google Drive config
            gdrive_config = AppSetting(
                key="gdrive_config",
                value={
                    "folder_id": settings.google_drive_folder_id or "",
                    "create_year_folders": True,
                    "create_month_folders": True,
                }
            )
            session.add(gdrive_config)

            await session.commit()
            print("      Default settings created!")
        else:
            print("      Settings already exist, skipping seed.")

    # Verify tables
    print("\n[3/3] Verifying database structure...")
    async with engine.connect() as conn:
        # List all tables
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]

        print(f"      Found {len(tables)} tables:")
        for table in tables:
            # Count rows
            count_result = await conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
            row_count = count_result.scalar()
            print(f"        - {table}: {row_count} rows")

    print("\n" + "=" * 50)
    print("Database initialization complete!")
    print("=" * 50)


async def reset_database():
    """Drop all tables and recreate them (USE WITH CAUTION!)."""
    print("WARNING: This will delete all data!")
    confirm = input("Type 'RESET' to confirm: ")

    if confirm != "RESET":
        print("Aborted.")
        return

    print("\nDropping all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    print("Recreating tables...")
    await init_database()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database initialization script")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables (destructive!)"
    )
    args = parser.parse_args()

    if args.reset:
        asyncio.run(reset_database())
    else:
        asyncio.run(init_database())
