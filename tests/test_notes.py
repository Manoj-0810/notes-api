"""Notes CRUD endpoint tests.

Covers:
- Create, read, update, delete notes
- Ownership and access control
- Pagination
- Full-text search
- Version history on update
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NoteVersion
from tests.conftest import create_test_note, create_test_user, get_auth_headers


class TestCreateNote:
    """POST /notes tests."""

    async def test_create_note_returns_201(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Creating a note returns 201 with note data."""
        user = await create_test_user(db_session)

        response = await client.post(
            "/notes",
            json={"title": "My Note", "content": "Hello world"},
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Note"
        assert data["content"] == "Hello world"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_note_validation_errors(self, client: AsyncClient, db_session: AsyncSession):
        """Invalid note data returns 422."""
        user = await create_test_user(db_session)

        # Empty title
        response = await client.post(
            "/notes",
            json={"title": ""},
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 422

        # Title too long (> 500 chars)
        response = await client.post(
            "/notes",
            json={"title": "x" * 1000},
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 422

    async def test_create_note_with_tags(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Creating a note with tags attaches them."""
        user = await create_test_user(db_session)

        response = await client.post(
            "/notes",
            json={
                "title": "Tagged Note",
                "content": "Content",
                "tags": ["work", "idea"],
            },
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 201

        # Tags should be retrievable
        tags_response = await client.get(
            "/tags",
            headers=get_auth_headers(user.id),
        )
        assert tags_response.status_code == 200
        tags = tags_response.json()
        tag_names = [t["name"] for t in tags]
        assert "work" in tag_names
        assert "idea" in tag_names


class TestGetNotes:
    """GET /notes tests."""

    async def test_get_all_notes_only_returns_own(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Note list only shows notes owned by or shared with the user."""
        user_a = await create_test_user(db_session, email="a@example.com")
        user_b = await create_test_user(db_session, email="b@example.com")

        await create_test_note(db_session, owner_id=user_a.id, title="A's Note")
        await create_test_note(db_session, owner_id=user_b.id, title="B's Note")

        response = await client.get(
            "/notes",
            headers=get_auth_headers(user_a.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "A's Note"

    async def test_get_note_by_id_own_note(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Owner can get their own note by ID."""
        user = await create_test_user(db_session)
        note = await create_test_note(db_session, owner_id=user.id, title="My Note")

        response = await client.get(
            f"/notes/{note.id}",
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "My Note"

    async def test_get_note_by_id_other_user_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accessing another user's note returns 403 (not 404)."""
        user_a = await create_test_user(db_session, email="a2@example.com")
        user_b = await create_test_user(db_session, email="b2@example.com")

        note = await create_test_note(db_session, owner_id=user_a.id)

        response = await client.get(
            f"/notes/{note.id}",
            headers=get_auth_headers(user_b.id),
        )
        assert response.status_code == 403

    async def test_get_nonexistent_note_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Getting a note that doesn't exist returns 404."""
        user = await create_test_user(db_session)
        import uuid

        response = await client.get(
            f"/notes/{uuid.uuid4()}",
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 404


class TestUpdateNote:
    """PUT /notes/{id} tests."""

    async def test_update_note_creates_version(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Updating a note saves the previous version."""
        user = await create_test_user(db_session)
        note = await create_test_note(
            db_session, owner_id=user.id, title="Original", content="Original content"
        )

        response = await client.put(
            f"/notes/{note.id}",
            json={"title": "Updated", "content": "Updated content"},
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"

        # Check version was created
        result = await db_session.execute(
            select(NoteVersion).where(NoteVersion.note_id == note.id)
        )
        versions = result.scalars().all()
        assert len(versions) == 1
        assert versions[0].title == "Original"
        assert versions[0].content == "Original content"

    async def test_update_other_user_note_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Updating another user's note returns 403."""
        user_a = await create_test_user(db_session, email="a3@example.com")
        user_b = await create_test_user(db_session, email="b3@example.com")
        note = await create_test_note(db_session, owner_id=user_a.id)

        response = await client.put(
            f"/notes/{note.id}",
            json={"title": "Hacked!"},
            headers=get_auth_headers(user_b.id),
        )
        assert response.status_code == 403


class TestDeleteNote:
    """DELETE /notes/{id} tests."""

    async def test_delete_note_returns_204(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Deleting a note returns 204 No Content."""
        user = await create_test_user(db_session)
        note = await create_test_note(db_session, owner_id=user.id)

        response = await client.delete(
            f"/notes/{note.id}",
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 204

        # Note should be gone
        get_response = await client.get(
            f"/notes/{note.id}",
            headers=get_auth_headers(user.id),
        )
        assert get_response.status_code == 404

    async def test_delete_other_user_note_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Deleting another user's note returns 403."""
        user_a = await create_test_user(db_session, email="a4@example.com")
        user_b = await create_test_user(db_session, email="b4@example.com")
        note = await create_test_note(db_session, owner_id=user_a.id)

        response = await client.delete(
            f"/notes/{note.id}",
            headers=get_auth_headers(user_b.id),
        )
        assert response.status_code == 403


class TestPagination:
    """GET /notes pagination tests."""

    async def test_pagination_params(self, client: AsyncClient, db_session: AsyncSession):
        """Pagination returns correct total, page, and pages."""
        user = await create_test_user(db_session)

        # Create 5 notes
        for i in range(5):
            await create_test_note(db_session, owner_id=user.id, title=f"Note {i}")

        # Page 1, limit 2
        response = await client.get(
            "/notes?page=1&limit=2",
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["pages"] == 3
        assert len(data["items"]) == 2

        # Page 2
        response = await client.get(
            "/notes?page=2&limit=2",
            headers=get_auth_headers(user.id),
        )
        data = response.json()
        assert data["page"] == 2
        assert len(data["items"]) == 2


class TestSearch:
    """GET /search tests."""

    async def test_search_by_keyword(self, client: AsyncClient, db_session: AsyncSession):
        """Search returns notes matching title or content."""
        user = await create_test_user(db_session)

        await create_test_note(db_session, owner_id=user.id, title="Python Tips", content="Code")
        await create_test_note(db_session, owner_id=user.id, title="Other", content="Python is great")
        await create_test_note(db_session, owner_id=user.id, title="Unrelated", content="Nothing here")

        response = await client.get(
            "/search?q=python",
            headers=get_auth_headers(user.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        titles = [n["title"] for n in data["results"]]
        assert "Python Tips" in titles
        assert "Other" in titles
