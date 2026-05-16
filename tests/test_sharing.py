"""Note sharing endpoint tests.

Covers:
- Sharing with valid user
- Shared user can read but not update/delete
- Edge cases: nonexistent user, self-sharing, sharing others' notes
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NoteShare
from tests.conftest import create_test_note, create_test_user, get_auth_headers


class TestShareNote:
    """POST /notes/{id}/share tests."""

    async def test_share_note_with_valid_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sharing a note with a valid user succeeds."""
        owner = await create_test_user(db_session, email="owner@example.com")
        sharee = await create_test_user(db_session, email="sharee@example.com")
        note = await create_test_note(db_session, owner_id=owner.id)

        response = await client.post(
            f"/notes/{note.id}/share",
            json={"share_with_email": "sharee@example.com"},
            headers=get_auth_headers(owner.id),
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Note shared successfully"

    async def test_shared_user_can_read_note(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """A user a note is shared with can GET the note."""
        owner = await create_test_user(db_session, email="owner2@example.com")
        sharee = await create_test_user(db_session, email="sharee2@example.com")
        note = await create_test_note(
            db_session, owner_id=owner.id, title="Shared Note", content="Secret"
        )

        # Share
        await client.post(
            f"/notes/{note.id}/share",
            json={"share_with_email": "sharee2@example.com"},
            headers=get_auth_headers(owner.id),
        )

        # Sharee can read
        response = await client.get(
            f"/notes/{note.id}",
            headers=get_auth_headers(sharee.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Shared Note"

    async def test_shared_user_cannot_update_note(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """A sharee cannot update a shared note (read-only access)."""
        owner = await create_test_user(db_session, email="owner3@example.com")
        sharee = await create_test_user(db_session, email="sharee3@example.com")
        note = await create_test_note(db_session, owner_id=owner.id)

        # Share
        await client.post(
            f"/notes/{note.id}/share",
            json={"share_with_email": "sharee3@example.com"},
            headers=get_auth_headers(owner.id),
        )

        # Sharee cannot update
        response = await client.put(
            f"/notes/{note.id}",
            json={"title": "Hacked!"},
            headers=get_auth_headers(sharee.id),
        )
        assert response.status_code == 403

    async def test_shared_user_cannot_delete_note(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """A sharee cannot delete a shared note."""
        owner = await create_test_user(db_session, email="owner4@example.com")
        sharee = await create_test_user(db_session, email="sharee4@example.com")
        note = await create_test_note(db_session, owner_id=owner.id)

        # Share
        await client.post(
            f"/notes/{note.id}/share",
            json={"share_with_email": "sharee4@example.com"},
            headers=get_auth_headers(owner.id),
        )

        # Sharee cannot delete
        response = await client.delete(
            f"/notes/{note.id}",
            headers=get_auth_headers(sharee.id),
        )
        assert response.status_code == 403

    async def test_share_with_nonexistent_email_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sharing with a nonexistent user email returns 404."""
        owner = await create_test_user(db_session)
        note = await create_test_note(db_session, owner_id=owner.id)

        response = await client.post(
            f"/notes/{note.id}/share",
            json={"share_with_email": "nobody@example.com"},
            headers=get_auth_headers(owner.id),
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_share_with_self_returns_400(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sharing a note with yourself returns 400 Bad Request."""
        owner = await create_test_user(db_session, email="self@example.com")
        note = await create_test_note(db_session, owner_id=owner.id)

        response = await client.post(
            f"/notes/{note.id}/share",
            json={"share_with_email": "self@example.com"},
            headers=get_auth_headers(owner.id),
        )
        assert response.status_code == 400
        assert "yourself" in response.json()["detail"].lower()

    async def test_share_note_you_dont_own_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Trying to share someone else's note returns 403."""
        owner = await create_test_user(db_session, email="real@example.com")
        hacker = await create_test_user(db_session, email="hacker@example.com")
        target = await create_test_user(db_session, email="target@example.com")
        note = await create_test_note(db_session, owner_id=owner.id)

        response = await client.post(
            f"/notes/{note.id}/share",
            json={"share_with_email": "target@example.com"},
            headers=get_auth_headers(hacker.id),
        )
        assert response.status_code == 403
