"""Authentication endpoints: register, login, refresh, me."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_session
from app.auth.dependencies import get_auth_context
from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.core.errors import AuthenticationError, ValidationError
from app.models.identity import Membership, Organization, User
from app.schemas.auth import (
    LoginRequest,
    MeOut,
    OrganizationOut,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.security.passwords import hash_password, validate_password_strength, verify_password
from app.services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or f"org-{uuid.uuid4().hex[:8]}"


def _token_pair(user: User, *, org_id: uuid.UUID | None, role: str | None) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), org_id=str(org_id) if org_id else None, role=role),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, session: AsyncSession = Depends(get_session)
) -> TokenPair:
    ok, reason = validate_password_strength(payload.password)
    if not ok:
        raise ValidationError(reason)

    existing = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if existing is not None:
        raise ValidationError("An account with that email already exists.")

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name or payload.email.split("@")[0],
        display_name=payload.full_name or payload.email.split("@")[0],
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    await session.flush()

    org_name = payload.organization_name or f"{user.display_name}'s Workspace"
    org = Organization(name=org_name, slug=_slugify(org_name))
    # Ensure slug uniqueness.
    if await session.scalar(select(Organization).where(Organization.slug == org.slug)):
        org.slug = f"{org.slug}-{uuid.uuid4().hex[:6]}"
    session.add(org)
    await session.flush()

    session.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
    await audit.record_audit(
        session,
        action="auth.register",
        user_id=user.id,
        organization_id=org.id,
        outcome="success",
    )
    await session.commit()
    return _token_pair(user, org_id=org.id, role="owner")


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        await audit.record_audit(
            session, action="auth.login", outcome="failure", detail={"email": payload.email}
        )
        await session.commit()
        raise AuthenticationError("Invalid email or password.")
    if not user.is_active:
        raise AuthenticationError("This account is disabled.")

    membership = await session.scalar(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    await audit.record_audit(
        session,
        action="auth.login",
        user_id=user.id,
        organization_id=membership.organization_id if membership else None,
        outcome="success",
    )
    await session.commit()
    return _token_pair(
        user,
        org_id=membership.organization_id if membership else None,
        role=membership.role if membership else None,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> TokenPair:
    decoded = decode_token(payload.refresh_token, expected_type="refresh")
    subject = decoded.get("sub")
    if not subject:
        raise AuthenticationError("Invalid refresh token.")
    user = await session.get(User, uuid.UUID(subject))
    if user is None or not user.is_active:
        raise AuthenticationError("User no longer exists or is inactive.")
    membership = await session.scalar(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    return _token_pair(
        user,
        org_id=membership.organization_id if membership else None,
        role=membership.role if membership else None,
    )


@router.get("/me", response_model=MeOut)
async def me(ctx: AuthContext = Depends(get_auth_context)) -> MeOut:
    return MeOut(
        user=UserOut.model_validate(ctx.user),
        organization=OrganizationOut.model_validate(ctx.organization),
        role=ctx.role,
    )