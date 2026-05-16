"""Authentication endpoint tests.

Covers:
- Registration (success, duplicate email, invalid input)
- Login (success, wrong password, nonexistent user)
- Token validation (missing, expired, malformed)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import create_test_user, get_auth_headers


class TestRegister:
    """POST /register tests."""

    async def test_register_success_returns_201(self, client: AsyncClient):
        """Successful registration returns 201 with success message."""
        response = await client.post(
            "/register",
            json={"email": "new@example.com", "password": "password123"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "User registered successfully"

    async def test_register_duplicate_email_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Registering with existing email returns 409 Conflict."""
        await create_test_user(db_session, email="dup@example.com")

        response = await client.post(
            "/register",
            json={"email": "dup@example.com", "password": "password123"},
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        """Invalid email format returns 422 validation error."""
        response = await client.post(
            "/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert response.status_code == 422

    async def test_register_short_password_returns_422(self, client: AsyncClient):
        """Password shorter than 8 characters returns 422."""
        response = await client.post(
            "/register",
            json={"email": "valid@example.com", "password": "1234567"},
        )
        assert response.status_code == 422


class TestLogin:
    """POST /login tests."""

    async def test_login_success_returns_jwt(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Valid credentials return a JWT access token."""
        await create_test_user(db_session, email="login@example.com", password="secret123")

        response = await client.post(
            "/login",
            json={"email": "login@example.com", "password": "secret123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    async def test_login_wrong_password_returns_401(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Wrong password returns 401 Unauthorized."""
        await create_test_user(db_session, email="wrong@example.com", password="correct123")

        response = await client.post(
            "/login",
            json={"email": "wrong@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_login_nonexistent_email_returns_401(self, client: AsyncClient):
        """Login with email that doesn't exist returns 401."""
        response = await client.post(
            "/login",
            json={"email": "ghost@example.com", "password": "anypassword"},
        )
        assert response.status_code == 401


class TestTokenValidation:
    """JWT validation tests via protected endpoints."""

    async def test_no_auth_header_returns_401(self, client: AsyncClient):
        """Request without Authorization header returns 401."""
        response = await client.get("/notes")
        assert response.status_code == 401

    async def test_malformed_jwt_returns_401(self, client: AsyncClient):
        """Malformed JWT token returns 401."""
        response = await client.get(
            "/notes",
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
        assert response.status_code == 401

    async def test_expired_jwt_returns_401(self, client: AsyncClient):
        """Expired JWT token returns 401.

        We create a token with a past expiration date.
        """
        from datetime import datetime, timedelta, timezone

        from jose import jwt
        from app.config import settings

        # Create a token that expired 1 hour ago
        expired = datetime.now(timezone.utc) - timedelta(hours=1)
        token = jwt.encode(
            {"sub": "some-user-id", "exp": expired},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

        response = await client.get(
            "/notes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
