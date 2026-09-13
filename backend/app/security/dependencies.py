"""FastAPI authentication and authorization dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.security.auth import AuthenticationError, decode_access_token
from backend.app.security.rbac import Permission, Role, has_permission, requires_mfa


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated identity extracted from a validated access token."""

    subject: str
    role: Role
    mfa_verified: bool


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    """Validate the Bearer token and return its authenticated principal."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        role = Role(payload["role"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token contains an invalid role.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return Principal(
        subject=str(payload["sub"]),
        role=role,
        mfa_verified=bool(payload.get("mfa", False)),
    )


def require_permission(
    permission: Permission,
) -> Callable[..., Principal]:
    """Create a FastAPI dependency enforcing one explicit permission."""

    async def dependency(
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        if not has_permission(principal.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}",
            )

        if requires_mfa(permission) and not principal.mfa_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA verification required for this sensitive operation.",
            )

        return principal

    return dependency
