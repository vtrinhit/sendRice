#!/usr/bin/env python3
"""
Admin User Creation Script
Creates or updates an admin user for authentication.
"""
import asyncio
import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import engine, Base, async_session_maker
from app.models.user import User
from app.services.auth_service import get_password_hash


async def create_admin(username: str, password: str, full_name: str | None = None):
    """Create or update an admin user."""
    print("=" * 50)
    print("SendRice Admin User Management")
    print("=" * 50)

    # Ensure tables exist
    print("\n[1/3] Ensuring database tables exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("      Tables verified!")

    # Create or update admin user
    print(f"\n[2/3] Creating/updating admin user '{username}'...")
    async with async_session_maker() as session:
        # Check if user exists
        result = await session.execute(
            select(User).where(User.username == username)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # Update existing user
            existing_user.hashed_password = get_password_hash(password)
            existing_user.is_admin = True
            existing_user.is_active = True
            if full_name:
                existing_user.full_name = full_name
            await session.commit()
            print(f"      Updated existing user '{username}'!")
        else:
            # Create new user
            new_user = User(
                username=username,
                hashed_password=get_password_hash(password),
                full_name=full_name or "Administrator",
                is_active=True,
                is_admin=True
            )
            session.add(new_user)
            await session.commit()
            print(f"      Created new admin user '{username}'!")

    # Verify
    print("\n[3/3] Verifying user...")
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        if user:
            print(f"      Username: {user.username}")
            print(f"      Full Name: {user.full_name}")
            print(f"      Is Admin: {user.is_admin}")
            print(f"      Is Active: {user.is_active}")

    print("\n" + "=" * 50)
    print("Admin user ready! You can now login at /login")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update admin user")
    parser.add_argument(
        "--username", "-u",
        type=str,
        default="admin",
        help="Admin username (default: admin)"
    )
    parser.add_argument(
        "--password", "-p",
        type=str,
        required=True,
        help="Admin password"
    )
    parser.add_argument(
        "--name", "-n",
        type=str,
        default=None,
        help="Full name (default: Administrator)"
    )

    args = parser.parse_args()

    if len(args.password) < 6:
        print("Error: Password must be at least 6 characters long")
        sys.exit(1)

    asyncio.run(create_admin(args.username, args.password, args.name))
