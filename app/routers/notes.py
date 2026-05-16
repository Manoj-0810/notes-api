"""Notes routes: all /notes/* endpoints plus /about.

This is the core of the application - CRUD, sharing, versioning, tagging,
search, and pagination all live here.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Note, NoteShare, NoteVersion, Tag, User, note_tags
from app.schemas import (
    AboutResponse,
    NoteCreateRequest,
    NoteListResponse,
    NoteResponse,
    NoteUpdateRequest,
    NoteVersionResponse,
    SearchResponse,
    ShareNoteRequest,
    ShareNoteResponse,
    TagResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Notes"])


# ---------------------------------------------------------------------------
# Helper: check note access permissions
# ---------------------------------------------------------------------------

async def _get_note_with_access(
    note_id: str,
    user: User,
    db: AsyncSession,
    require_owner: bool = False,
) -> Note:
    """Fetch a note and verify the user has access.

    Args:
        note_id: UUID of the note.
        user: Current authenticated user.
        db: Database session.
        require_owner: If True, only the owner can access (returns 403 for shared).

    Returns:
        The Note object.

    Raises:
        403: User doesn't have access, or needs owner but is only a sharee.
        404: Note doesn't exist (only after confirming user should see it).
    """
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.id == note_id)
    )
    note = result.scalar_one_or_none()

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    # Owner always has access
    if note.owner_id == user.id:
        return note

    # Check if note is shared with this user
    if not require_owner:
        share_result = await db.execute(
            select(NoteShare).where(
                NoteShare.note_id == note_id,
                NoteShare.shared_with == user.id,
            )
        )
        if share_result.scalar_one_or_none() is not None:
            return note

    # User has no access - return 403 (not 404) per spec
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have permission to access this note",
    )


async def _require_owner(note: Note, user: User) -> None:
    """Raise 403 if the user is not the note's owner."""
    if note.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the note owner can perform this action",
        )


# ---------------------------------------------------------------------------
# Helper: tag management
# ---------------------------------------------------------------------------

async def _set_note_tags(
    db: AsyncSession,
    note: Note,
    tag_names: Optional[List[str]],
    user_id: str,
) -> None:
    """Set tags on a note, creating them if they don't exist.

    Replaces any existing tags. Tags are per-user namespaced.
    Uses direct association table inserts to avoid lazy-load issues.
    """
    if tag_names is None:
        return

    # Normalize tag names
    normalized = [t.strip().lower() for t in tag_names if t.strip()]

    # Clear existing tag associations
    await db.execute(
        note_tags.delete().where(note_tags.c.note_id == note.id)
    )

    if not normalized:
        return

    # Get or create tags, then insert associations
    for tag_name in normalized:
        result = await db.execute(
            select(Tag).where(
                Tag.name == tag_name,
                Tag.user_id == user_id,
            )
        )
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=tag_name, user_id=user_id)
            db.add(tag)
            await db.flush()
        # Direct association table insert avoids ORM collection state issues
        await db.execute(
            note_tags.insert().values(note_id=note.id, tag_id=tag.id)
        )


async def _increment_version(db: AsyncSession, note: Note) -> None:
    """Save a version snapshot before updating a note.

    Appends to the immutable version history.
    """
    # Get next version number
    result = await db.execute(
        select(func.count(NoteVersion.id)).where(NoteVersion.note_id == note.id)
    )
    count = result.scalar() or 0

    version = NoteVersion(
        note_id=note.id,
        title=note.title,
        content=note.content,
        version_num=count + 1,
    )
    db.add(version)


# ---------------------------------------------------------------------------
# GET /about
# ---------------------------------------------------------------------------

@router.get(
    "/about",
    response_model=AboutResponse,
    summary="About the developer",
)
async def about(request: Request) -> AboutResponse:
    """Return developer information and feature descriptions."""
    return AboutResponse(
        name="[STUDENT NAME]",
        email="[STUDENT EMAIL]",
        my_features={
            "note_version_history": (
                "Every PUT /notes/{id} automatically saves the previous version "
                "before updating. Users can view history at GET /notes/{id}/versions "
                "and restore any version at POST /notes/{id}/restore/{version_num}. "
                "Chosen because data loss is a trust-destroying bug in productivity apps "
                "- this makes the app production-safe with zero UI overhead."
            ),
            "note_tagging_system": (
                "Notes accept optional tags on creation/update. Tags are user-namespaced "
                "and filterable via GET /notes?tag=work. Full tag management at GET /tags "
                "and DELETE /tags/{name}. Chosen because flat lists of notes don't scale "
                "- tags are the most flexible organizational primitive, more powerful than "
                "folders and simpler than full search for most use cases."
            ),
        },
    )


# ---------------------------------------------------------------------------
# GET /notes (list)
# ---------------------------------------------------------------------------

@router.get(
    "/notes",
    response_model=NoteListResponse,
    summary="List all accessible notes",
)
async def list_notes(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    tag: Optional[str] = Query(None, description="Filter by tag name"),
    q: Optional[str] = Query(None, description="Search query (searches title + content)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteListResponse:
    """List all notes the current user can access (owned + shared).

    Supports pagination, tag filtering, and full-text search.
    """
    # Build base query: notes owned by user OR shared with user
    # We use a union approach via OR condition
    owned_cond = Note.owner_id == user.id

    # Subquery for shared notes
    shared_subq = select(NoteShare.note_id).where(
        NoteShare.shared_with == user.id
    )

    conditions = [owned_cond | Note.id.in_(shared_subq)]

    # Tag filter
    if tag:
        tag_normalized = tag.strip().lower()
        tag_subq = (
            select(note_tags.c.note_id)
            .join(Tag, note_tags.c.tag_id == Tag.id)
            .where(
                Tag.name == tag_normalized,
                Tag.user_id == user.id,
            )
        )
        conditions.append(Note.id.in_(tag_subq))

    # Search filter (case-insensitive on title + content)
    if q:
        search_term = f"%{q}%"
        conditions.append(
            or_(
                Note.title.ilike(search_term),
                Note.content.ilike(search_term),
            )
        )

    # Count total
    count_result = await db.execute(
        select(func.count(Note.id)).where(*conditions)
    )
    total = count_result.scalar() or 0

    # Fetch paginated notes with tags
    offset = (page - 1) * limit
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(*conditions)
        .order_by(Note.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    notes = result.scalars().all()

    pages = (total + limit - 1) // limit if limit > 0 else 1

    return NoteListResponse(
        items=[
            NoteResponse(
                id=n.id,
                title=n.title,
                content=n.content,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in notes
        ],
        total=total,
        page=page,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# POST /notes (create)
# ---------------------------------------------------------------------------

@router.post(
    "/notes",
    status_code=status.HTTP_201_CREATED,
    response_model=NoteResponse,
    summary="Create a new note",
)
async def create_note(
    request: Request,
    data: NoteCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    """Create a new note owned by the current user.

    Optionally attach tags at creation time.
    """
    note = Note(
        owner_id=user.id,
        title=data.title,
        content=data.content,
    )
    db.add(note)
    await db.flush()

    # Handle tags
    await _set_note_tags(db, note, data.tags, user.id)

    await db.commit()
    await db.refresh(note)

    logger.info("Note created: %s by user %s", note.id, user.email)
    return NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /notes/{id} (detail)
# ---------------------------------------------------------------------------

@router.get(
    "/notes/{note_id}",
    response_model=NoteResponse,
    summary="Get a single note",
    responses={
        403: {"description": "Access denied"},
        404: {"description": "Note not found"},
    },
)
async def get_note(
    request: Request,
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    """Get a single note by ID.

    Accessible if user owns the note or it has been shared with them.
    """
    note = await _get_note_with_access(note_id, user, db)
    return NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# ---------------------------------------------------------------------------
# PUT /notes/{id} (update)
# ---------------------------------------------------------------------------

@router.put(
    "/notes/{note_id}",
    response_model=NoteResponse,
    summary="Update a note",
    responses={
        403: {"description": "Not owner or access denied"},
        404: {"description": "Note not found"},
    },
)
async def update_note(
    request: Request,
    note_id: str,
    data: NoteUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    """Update a note. Saves a version snapshot before updating.

    Only the owner can update. Shared users get 403.
    """
    note = await _get_note_with_access(note_id, user, db)
    await _require_owner(note, user)

    # Save version snapshot before modifying
    await _increment_version(db, note)

    # Apply updates
    if data.title is not None:
        note.title = data.title
    if data.content is not None:
        note.content = data.content

    # Handle tags (replace existing)
    if data.tags is not None:
        await _set_note_tags(db, note, data.tags, user.id)

    await db.commit()
    await db.refresh(note)

    logger.info("Note updated: %s by user %s", note.id, user.email)
    return NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# ---------------------------------------------------------------------------
# DELETE /notes/{id}
# ---------------------------------------------------------------------------

@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    responses={
        403: {"description": "Not owner or access denied"},
        404: {"description": "Note not found"},
    },
)
async def delete_note(
    request: Request,
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a note and all its versions/shares.

    Only the owner can delete. Returns 204 No Content on success.
    """
    note = await _get_note_with_access(note_id, user, db)
    await _require_owner(note, user)

    await db.delete(note)
    await db.commit()

    logger.info("Note deleted: %s by user %s", note_id, user.email)
    return None


# ---------------------------------------------------------------------------
# POST /notes/{id}/share
# ---------------------------------------------------------------------------

@router.post(
    "/notes/{note_id}/share",
    response_model=ShareNoteResponse,
    summary="Share a note with another user",
    responses={
        400: {"description": "Cannot share with yourself"},
        403: {"description": "Not owner or access denied"},
        404: {"description": "Note or user not found"},
    },
)
async def share_note(
    request: Request,
    note_id: str,
    data: ShareNoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareNoteResponse:
    """Share a note with another user by email.

    Only the owner can share. Cannot share with self.
    The sharee gets read-only access (no PUT/DELETE).
    """
    note = await _get_note_with_access(note_id, user, db)
    await _require_owner(note, user)

    # Cannot share with yourself
    if data.share_with_email.lower() == user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot share a note with yourself",
        )

    # Find the target user
    result = await db.execute(
        select(User).where(User.email == data.share_with_email.lower())
    )
    target_user = result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already shared
    existing = await db.execute(
        select(NoteShare).where(
            NoteShare.note_id == note_id,
            NoteShare.shared_with == target_user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        # Already shared - return success (idempotent)
        return ShareNoteResponse()

    share = NoteShare(
        note_id=note_id,
        shared_with=target_user.id,
        shared_by=user.id,
    )
    db.add(share)
    await db.commit()

    logger.info(
        "Note %s shared by %s with %s",
        note_id,
        user.email,
        data.share_with_email,
    )
    return ShareNoteResponse()


# ---------------------------------------------------------------------------
# GET /notes/{id}/versions
# ---------------------------------------------------------------------------

@router.get(
    "/notes/{note_id}/versions",
    response_model=List[NoteVersionResponse],
    summary="List version history",
    responses={
        403: {"description": "Access denied"},
        404: {"description": "Note not found"},
    },
)
async def list_versions(
    request: Request,
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[NoteVersionResponse]:
    """List all versions of a note, newest first.

    Only the owner can view version history.
    """
    note = await _get_note_with_access(note_id, user, db)
    await _require_owner(note, user)

    result = await db.execute(
        select(NoteVersion)
        .where(NoteVersion.note_id == note_id)
        .order_by(NoteVersion.version_num.desc())
    )
    versions = result.scalars().all()

    return [
        NoteVersionResponse(
            id=v.id,
            version_num=v.version_num,
            title=v.title,
            content=v.content,
            created_at=v.created_at,
        )
        for v in versions
    ]


# ---------------------------------------------------------------------------
# GET /notes/{id}/versions/{ver}
# ---------------------------------------------------------------------------

@router.get(
    "/notes/{note_id}/versions/{version_num}",
    response_model=NoteVersionResponse,
    summary="Get a specific version",
    responses={
        403: {"description": "Access denied"},
        404: {"description": "Note or version not found"},
    },
)
async def get_version(
    request: Request,
    note_id: str,
    version_num: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteVersionResponse:
    """Get a specific version by version number."""
    note = await _get_note_with_access(note_id, user, db)
    await _require_owner(note, user)

    result = await db.execute(
        select(NoteVersion).where(
            NoteVersion.note_id == note_id,
            NoteVersion.version_num == version_num,
        )
    )
    version = result.scalar_one_or_none()

    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    return NoteVersionResponse(
        id=version.id,
        version_num=version.version_num,
        title=version.title,
        content=version.content,
        created_at=version.created_at,
    )


# ---------------------------------------------------------------------------
# POST /notes/{id}/restore/{ver}
# ---------------------------------------------------------------------------

@router.post(
    "/notes/{note_id}/restore/{version_num}",
    response_model=NoteResponse,
    summary="Restore a note to a past version",
    responses={
        403: {"description": "Access denied"},
        404: {"description": "Note or version not found"},
    },
)
async def restore_version(
    request: Request,
    note_id: str,
    version_num: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    """Restore a note to a previous version.

    Saves the current state as a new version before restoring.
    """
    note = await _get_note_with_access(note_id, user, db)
    await _require_owner(note, user)

    # Find the version to restore
    result = await db.execute(
        select(NoteVersion).where(
            NoteVersion.note_id == note_id,
            NoteVersion.version_num == version_num,
        )
    )
    version = result.scalar_one_or_none()

    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    # Save current state before restoring
    await _increment_version(db, note)

    # Restore
    note.title = version.title
    note.content = version.content

    await db.commit()
    await db.refresh(note)

    logger.info("Note %s restored to version %d", note_id, version_num)
    return NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /tags
# ---------------------------------------------------------------------------

@router.get(
    "/tags",
    response_model=List[TagResponse],
    summary="List all tags for current user",
)
async def list_tags(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TagResponse]:
    """List all tags belonging to the current user."""
    result = await db.execute(
        select(Tag).where(Tag.user_id == user.id).order_by(Tag.name)
    )
    tags = result.scalars().all()

    return [TagResponse(id=t.id, name=t.name) for t in tags]


# ---------------------------------------------------------------------------
# DELETE /tags/{tag_name}
# ---------------------------------------------------------------------------

@router.delete(
    "/tags/{tag_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tag",
)
async def delete_tag(
    request: Request,
    tag_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a tag and remove it from all notes.

    Tag is identified by name (case-insensitive).
    """
    result = await db.execute(
        select(Tag).where(
            Tag.name == tag_name.strip().lower(),
            Tag.user_id == user.id,
        )
    )
    tag = result.scalar_one_or_none()

    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    await db.delete(tag)
    await db.commit()

    return None


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------

@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Full-text search across notes",
)
async def search_notes(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search across note titles and content.

    Returns notes owned by or shared with the current user.
    """
    search_term = f"%{q}%"

    owned_cond = Note.owner_id == user.id
    shared_subq = select(NoteShare.note_id).where(
        NoteShare.shared_with == user.id
    )

    result = await db.execute(
        select(Note)
        .where(
            (owned_cond | Note.id.in_(shared_subq))
            & (
                Note.title.ilike(search_term)
                | Note.content.ilike(search_term)
            )
        )
        .order_by(Note.updated_at.desc())
    )
    notes = result.scalars().all()

    return SearchResponse(
        query=q,
        results=[
            NoteResponse(
                id=n.id,
                title=n.title,
                content=n.content,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in notes
        ],
        total=len(notes),
    )
