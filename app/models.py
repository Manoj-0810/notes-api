"""SQLAlchemy ORM models.

All primary keys use UUID (harder to enumerate than integers).
Timestamps are timezone-aware via server defaults.
Relationships cascade properly to prevent orphaned rows.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship, validates

from app.database import Base


# SQLAlchemy 2.0+ compatible UUID column that works with both SQLite and PostgreSQL
def UUIDColumn(*args, **kwargs):
    """Create a UUID primary key column compatible with SQLite and PostgreSQL."""
    # Use String(36) as fallback for SQLite which doesn't have native UUID
    return Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        *args,
        **kwargs,
    )


class User(Base):
    """Application user with email/password authentication."""

    __tablename__ = "users"

    id = UUIDColumn()
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    notes = relationship(
        "Note",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tags = relationship(
        "Tag",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @validates("email")
    def validate_email(self, key: str, email: str) -> str:
        """Normalize email to lowercase."""
        return email.strip().lower()


class Note(Base):
    """A note owned by a user. Can be shared with other users."""

    __tablename__ = "notes"

    id = UUIDColumn()
    owner_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(500), nullable=False, default="")
    content = Column(Text, nullable=False, default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    owner = relationship("User", back_populates="notes", lazy="selectin")
    shares = relationship(
        "NoteShare",
        back_populates="note",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    versions = relationship(
        "NoteVersion",
        back_populates="note",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="desc(NoteVersion.version_num)",
    )
    tags = relationship(
        "Tag",
        secondary="note_tags",
        back_populates="notes",
        lazy="selectin",
    )


class NoteShare(Base):
    """Many-to-many link between notes and users they've been shared with."""

    __tablename__ = "note_shares"
    __table_args__ = (
        UniqueConstraint("note_id", "shared_with", name="uix_note_share"),
    )

    id = UUIDColumn()
    note_id = Column(
        String(36),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shared_with = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shared_by = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
    )
    shared_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    note = relationship("Note", back_populates="shares", lazy="selectin")
    shared_with_user = relationship(
        "User",
        foreign_keys=[shared_with],
        lazy="selectin",
    )
    shared_by_user = relationship(
        "User",
        foreign_keys=[shared_by],
        lazy="selectin",
    )


class NoteVersion(Base):
    """Immutable snapshot of a note before each update.

    Append-only audit trail for data recovery.
    """

    __tablename__ = "note_versions"

    id = UUIDColumn()
    note_id = Column(
        String(36),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    version_num = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    note = relationship("Note", back_populates="versions", lazy="selectin")


class Tag(Base):
    """User-scoped tag for organizing notes."""

    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uix_tag_name_user"),
    )

    id = UUIDColumn()
    name = Column(String(100), nullable=False, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    user = relationship("User", back_populates="tags", lazy="selectin")
    notes = relationship(
        "Note",
        secondary="note_tags",
        back_populates="tags",
        lazy="selectin",
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """Normalize tag name: lowercase, strip whitespace."""
        return name.strip().lower()


# Association table for Note <-> Tag many-to-many
note_tags = Table(
    "note_tags",
    Base.metadata,
    Column(
        "note_id",
        String(36),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        String(36),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
