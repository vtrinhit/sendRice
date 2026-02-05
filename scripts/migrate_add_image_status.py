"""
Migration script to add image_status and image_error columns to employees table.
Run this script to update the database schema.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine


async def migrate():
    """Add image_status and image_error columns to employees table."""
    async with engine.begin() as conn:
        # Check if columns exist
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'employees'
            AND column_name IN ('image_status', 'image_error')
        """))
        existing_columns = [row[0] for row in result.fetchall()]

        if 'image_status' not in existing_columns:
            print("Adding image_status column...")
            await conn.execute(text("""
                ALTER TABLE employees
                ADD COLUMN image_status VARCHAR(20) DEFAULT 'pending'
            """))
            print("Added image_status column")
        else:
            print("image_status column already exists")

        if 'image_error' not in existing_columns:
            print("Adding image_error column...")
            await conn.execute(text("""
                ALTER TABLE employees
                ADD COLUMN image_error TEXT
            """))
            print("Added image_error column")
        else:
            print("image_error column already exists")

        print("Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
