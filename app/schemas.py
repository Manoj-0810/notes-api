"""Pydantic v2 request/response schemas.

Separates API contracts from ORM models.
All schemas use from_attributes=True for ORM compatibility.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    """POST /register request body."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        description="Password (minimum 8 characters)",
    )


class UserLoginRequest(BaseModel):
    """POST /login request body."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User data exposed in responses (no password!)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    created_at: datetime
    is_active: bool


# ---------------------------------------------------------------------------
# Note schemas
# ---------------------------------------------------------------------------

class NoteCreateRequest(BaseModel):
    """POST /notes request body."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Note title (1-500 characters)",
    )
    content: str = Field(
        default="",
        description="Note content (supports markdown)",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Optional list of tag names",
    )


class NoteUpdateRequest(BaseModel):
    """PUT /notes/{id} request body."""

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Note title (1-500 characters)",
    )
    content: Optional[str] = Field(
        default=None,
        description="Note content",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Optional list of tag names (replaces existing tags)",
    )


class NoteResponse(BaseModel):
    """Single note response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    """Paginated list of notes."""

    items: List[NoteResponse]
    total: int
    page: int
    pages: int


# ---------------------------------------------------------------------------
# Sharing schemas
# ---------------------------------------------------------------------------

class ShareNoteRequest(BaseModel):
    """POST /notes/{id}/share request body."""

    share_with_email: EmailStr = Field(
        ...,
        description="Email of the user to share with",
    )


class ShareNoteResponse(BaseModel):
    """Successful share response."""

    message: str = "Note shared successfully"


# ---------------------------------------------------------------------------
# Version history schemas
# ---------------------------------------------------------------------------

class NoteVersionResponse(BaseModel):
    """A single version snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    version_num: int
    title: str
    content: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Tag schemas
# ---------------------------------------------------------------------------

class TagResponse(BaseModel):
    """Tag with note count."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


# ---------------------------------------------------------------------------
# About / search schemas
# ---------------------------------------------------------------------------

class AboutResponse(BaseModel):
    """GET /about response."""

    name: str
    email: str
    my_features: dict


class SearchResponse(BaseModel):
    """GET /search response."""

    query: str
    results: List[NoteResponse]
    total: int
