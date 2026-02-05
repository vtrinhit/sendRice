#!/usr/bin/env python3
"""
Migration Script: Add file_path to import_sessions
Run this script to add the file_path column to existing databases.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


async def migrate():
    """Add file_path column to import_sessions table."""
    print("=" * 50)
    print("Migration: Add file_path to import_sessions")
    print("=" * 50)

    async with engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'import_sessions'
            AND column_name = 'file_path'
        """))
        exists = result.fetchone() is not None

        if exists:
            print("\n[INFO] Column 'file_path' already exists. Skipping.")
        else:
            print("\n[1/1] Adding 'file_path' column to import_sessions...")
            await conn.execute(text("""
                ALTER TABLE import_sessions
                ADD COLUMN file_path VARCHAR(500) NULL
            """))
            print("      Column added successfully!")

    print("\n" + "=" * 50)
    print("Migration complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(migrate())
