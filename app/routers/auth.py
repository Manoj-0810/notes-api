"""Authentication routes: /register, /login."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    summary="Register a new user",
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Validation error (email format, password length)"},
    },
)
async def register(
    request: Request,
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a new user with email and password.

    Password is hashed with bcrypt before storage.
    Returns 409 Conflict if email already exists.
    """
    # Check if email already exists (explicit check for cleaner error)
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user with hashed password
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        # Race condition: unique constraint failed
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    logger.info("User registered: %s", data.email)
    return {"message": "User registered successfully"}


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=TokenResponse,
    summary="Login and receive JWT",
    responses={
        401: {"description": "Invalid email or password"},
        422: {"description": "Validation error"},
    },
)
async def login(
    request: Request,
    data: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return a JWT access token.

    Token expires after 30 minutes (configurable via ACCESS_TOKEN_EXPIRE_MINUTES).
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    # Generic error message to prevent user enumeration attacks
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate JWT
    access_token = create_access_token(data={"sub": str(user.id)})

    logger.info("User logged in: %s", data.email)
    return TokenResponse(access_token=access_token)
