"""Authentication API for ResQShield."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.users import User
from backend.app.security.auth import (
    create_access_token,
    verify_mfa_code,
    verify_password,
)
from backend.app.security.dependencies import Principal, get_current_principal
from backend.app.security.rbac import Role


router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    mfa_verified: bool


class CurrentUserResponse(BaseModel):
    subject: str
    role: str
    mfa_verified: bool


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user and issue a signed access token."""

    result = await db.execute(
        select(User).where(User.email == request.email.lower())
    )
    user = result.scalar_one_or_none()

    if (
        user is None
        or not user.is_active
        or not user.password_hash
        or not verify_password(request.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    try:
        role = Role(user.role_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has an invalid platform role.",
        ) from exc

    mfa_verified = False

    if user.mfa_enabled:
        if not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA is enabled but the account has no MFA secret.",
            )

        if request.mfa_code is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA code required.",
            )

        if not verify_mfa_code(
            secret=user.mfa_secret,
            code=request.mfa_code,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code.",
            )

        mfa_verified = True

    token = create_access_token(
        subject=user.email,
        role=role.value,
        mfa_verified=mfa_verified,
    )

    return TokenResponse(
        access_token=token,
        role=role.value,
        mfa_verified=mfa_verified,
    )


@router.get("/me", response_model=CurrentUserResponse)
async def current_user(
    principal: Principal = Depends(get_current_principal),
) -> CurrentUserResponse:
    """Return the identity represented by the current Bearer token."""

    return CurrentUserResponse(
        subject=principal.subject,
        role=principal.role.value,
        mfa_verified=principal.mfa_verified,
    )
