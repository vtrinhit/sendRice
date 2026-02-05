"""
Migration script to add index on image_status column in employees table.
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
    """Add index on image_status column in employees table."""
    index_name = "ix_employees_image_status"

    async with engine.begin() as conn:
        # Check if index already exists
        result = await conn.execute(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'employees'
            AND indexname = :index_name
        """), {"index_name": index_name})

        existing_index = result.fetchone()

        if existing_index is None:
            print(f"Creating index {index_name}...")
            await conn.execute(text(f"""
                CREATE INDEX {index_name}
                ON employees (image_status)
            """))
            print(f"Created index {index_name}")
        else:
            print(f"Index {index_name} already exists")

        print("Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
