"""FastAPI auth dependencies: current user, current organization, role checks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.db.session import get_session
from app.models.identity import Membership, Organization, User


@dataclass
class AuthContext:
    """Resolved authentication + tenancy context for a request."""

    user: User
    organization: Organization
    role: str

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def organization_id(self) -> uuid.UUID:
        return self.organization.id


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Missing or malformed Authorization header.")
    return authorization.split(" ", 1)[1].strip()


async def get_auth_context(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    """Resolve the authenticated user + active organization from a bearer token."""
    token = _extract_bearer(authorization)
    payload = decode_token(token, expected_type="access")

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Token is missing a subject.")

    try:
        user_id = uuid.UUID(subject)
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("Token subject is invalid.") from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User no longer exists or is inactive.")

    org_id_raw = payload.get("org_id")
    membership: Membership | None = None
    if org_id_raw:
        try:
            org_id = uuid.UUID(org_id_raw)
        except (ValueError, TypeError):
            org_id = None
        if org_id:
            membership = await session.scalar(
                select(Membership).where(
                    Membership.user_id == user_id, Membership.organization_id == org_id
                )
            )

    if membership is None:
        membership = await session.scalar(
            select(Membership).where(Membership.user_id == user_id).limit(1)
        )
    if membership is None:
        raise PermissionDeniedError("User is not a member of any organization.")

    organization = await session.get(Organization, membership.organization_id)
    if organization is None:
        raise PermissionDeniedError("Organization not found.")

    return AuthContext(user=user, organization=organization, role=membership.role)


def require_roles(*roles: str):
    """Dependency factory enforcing that the user holds one of ``roles``."""

    async def _dependency(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if roles and ctx.role not in roles and not ctx.user.is_superuser:
            raise PermissionDeniedError(
                f"This action requires one of: {', '.join(roles)}."
            )
        return ctx

    return _dependency