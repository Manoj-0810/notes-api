"""Pytest fixtures for the Notes API test suite.

Provides:
- async client for HTTP requests
- database session management with rollback after each test
- factories for creating test users and notes
"""

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Set test environment before importing app code
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ENVIRONMENT"] = "development"

from app.auth import create_access_token, hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Note, User  # noqa: E402

# Test async engine (in-memory SQLite)
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = sessionmaker(
    test_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def create_tables():
    """Create all tables in the test database."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """Drop all tables from the test database."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Provide a session-scoped event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh database session for each test.

    Tables are created before each test and dropped after.
    """
    await create_tables()

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    await drop_tables()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP client with database override.

    All requests go through the same DB session so data is visible.
    """
    async def override_get_db():
        yield db_session

    # Override the dependency
    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Restore original override
    if original_override is not None:
        app.dependency_overrides[get_db] = original_override
    else:
        del app.dependency_overrides[get_db]


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

async def create_test_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "password123",
) -> User:
    """Create a test user in the database."""
    user = User(
        email=email,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def get_auth_headers(user_id: str) -> dict:
    """Generate Authorization header for a user."""
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


async def create_test_note(
    db: AsyncSession,
    owner_id: str,
    title: str = "Test Note",
    content: str = "Test content",
) -> Note:
    """Create a test note in the database."""
    note = Note(
        owner_id=owner_id,
        title=title,
        content=content,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note
