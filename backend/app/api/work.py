"""Work endpoints: dashboard, timeline, inbox, calendar, teams, tasks, commitments.

All reads are scoped to the caller's organization and support pagination so the
browser never receives thousands of rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, Page, get_session, pagination
from app.auth.dependencies import get_auth_context
from app.core.errors import NotFoundError
from app.models.enums import CommitmentStatus, TaskStatus
from app.models.operations import Commitment
from app.models.work import CalendarEvent, Email, Message, Project, Task
from app.schemas.dashboard import DashboardResponse
from app.schemas.work import (
    CalendarEventOut,
    CommitmentOut,
    EmailOut,
    MessageOut,
    Paginated,
    TaskOut,
    TimelineItem,
    TimelineResponse,
)
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/api", tags=["work"])


def _email_out(email: Email) -> EmailOut:
    import json

    try:
        to = json.loads(email.to_recipients or "[]")
    except json.JSONDecodeError:
        to = []
    return EmailOut(
        id=email.id,
        source=email.source,
        external_id=email.external_id,
        subject=email.subject,
        body_preview=email.body_preview,
        sender_email=email.sender_email,
        sender_name=email.sender_name,
        to_recipients=to,
        received_at=email.received_at,
        is_read=email.is_read,
        has_attachments=email.has_attachments,
        priority=email.priority,
        needs_reply=email.needs_reply,
        is_important=email.is_important,
        project_id=email.project_id,
        web_link=email.web_link,
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    return await dashboard_service.build_dashboard(
        session,
        organization_id=ctx.organization_id,
        user_name=ctx.user.display_name or ctx.user.full_name,
    )


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    limit: int = Query(default=50, ge=1, le=200),
    sources: str | None = Query(default=None, description="Comma-separated sources"),
    days: int = Query(default=7, ge=1, le=90),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> TimelineResponse:
    source_list = [s.strip() for s in sources.split(",")] if sources else None
    since = datetime.now(timezone.utc) - timedelta(days=days)
    items = await dashboard_service.build_timeline(
        session,
        organization_id=ctx.organization_id,
        limit=limit,
        sources=source_list,
        since=since,
    )
    return TimelineResponse(items=items, next_cursor=None)


@router.get("/emails", response_model=Paginated)
async def list_emails(
    page: Page = Depends(pagination),
    important: bool | None = Query(default=None),
    needs_reply: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> Paginated:
    stmt = select(Email).where(Email.organization_id == ctx.organization_id)
    if important is not None:
        stmt = stmt.where(Email.is_important.is_(important))
    if needs_reply is not None:
        stmt = stmt.where(Email.needs_reply.is_(needs_reply))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Email.subject.ilike(like),
                Email.body_preview.ilike(like),
                Email.sender_email.ilike(like),
                Email.sender_name.ilike(like),
            )
        )
    total = int(
        await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    rows = await session.scalars(
        stmt.order_by(desc(Email.received_at)).offset(page.offset).limit(page.page_size)
    )
    return Paginated(
        items=[_email_out(e).model_dump(mode="json") for e in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/emails/{email_id}", response_model=EmailOut)
async def get_email(
    email_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> EmailOut:
    email = await session.get(Email, email_id)
    if email is None or email.organization_id != ctx.organization_id:
        raise NotFoundError("Email not found.")
    return _email_out(email)


@router.get("/calendar", response_model=list[CalendarEventOut])
async def list_calendar(
    days: int = Query(default=7, ge=1, le=90),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[CalendarEventOut]:
    now = datetime.now(timezone.utc)
    rows = await session.scalars(
        select(CalendarEvent)
        .where(
            CalendarEvent.organization_id == ctx.organization_id,
            CalendarEvent.ends_at >= now,
            CalendarEvent.starts_at <= now + timedelta(days=days),
        )
        .order_by(CalendarEvent.starts_at)
        .limit(200)
    )
    return [CalendarEventOut.model_validate(e) for e in rows]


@router.get("/messages", response_model=Paginated)
async def list_messages(
    page: Page = Depends(pagination),
    search: str | None = Query(default=None),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> Paginated:
    stmt = select(Message).where(Message.organization_id == ctx.organization_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(Message.body.ilike(like), Message.conversation_name.ilike(like),
                Message.sender_name.ilike(like))
        )
    total = int(
        await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    rows = await session.scalars(
        stmt.order_by(desc(Message.sent_at)).offset(page.offset).limit(page.page_size)
    )
    return Paginated(
        items=[MessageOut.model_validate(m).model_dump(mode="json") for m in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/tasks", response_model=Paginated)
async def list_tasks(
    page: Page = Depends(pagination),
    status: str | None = Query(default=None),
    overdue: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> Paginated:
    stmt = select(Task).where(Task.organization_id == ctx.organization_id)
    if status:
        stmt = stmt.where(Task.status == status)
    if overdue is not None:
        stmt = stmt.where(Task.is_overdue.is_(overdue))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Task.title.ilike(like), Task.description.ilike(like)))
    total = int(
        await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    rows = await session.scalars(
        stmt.order_by(desc(Task.is_overdue), Task.due_at).offset(page.offset).limit(page.page_size)
    )
    return Paginated(
        items=[TaskOut.model_validate(t).model_dump(mode="json") for t in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/projects", response_model=list[dict])
async def list_projects(
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await session.scalars(
        select(Project)
        .where(Project.organization_id == ctx.organization_id, Project.is_archived.is_(False))
        .order_by(Project.name)
        .limit(200)
    )
    return [
        {"id": str(p.id), "name": p.name, "description": p.description, "source": p.source}
        for p in rows
    ]


@router.get("/commitments", response_model=list[CommitmentOut])
async def list_commitments(
    direction: str | None = Query(default=None, description="i_owe | owed_to_me"),
    status: str | None = Query(default=None),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[CommitmentOut]:
    stmt = select(Commitment).where(Commitment.organization_id == ctx.organization_id)
    if direction:
        stmt = stmt.where(Commitment.direction == direction)
    if status:
        stmt = stmt.where(Commitment.status == status)
    rows = await session.scalars(stmt.order_by(Commitment.due_at).limit(100))
    return [CommitmentOut.model_validate(c) for c in rows]


@router.post("/commitments/scan")
async def scan_commitments(
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    from app.services import commitments as commitments_service

    created_emails = await commitments_service.scan_emails(
        session, organization_id=ctx.organization_id, user_email=ctx.user.email
    )
    created_messages = await commitments_service.scan_messages(
        session, organization_id=ctx.organization_id, user_email=ctx.user.email
    )
    overdue = await commitments_service.refresh_overdue(
        session, organization_id=ctx.organization_id
    )
    await session.commit()
    return {
        "from_emails": created_emails,
        "from_messages": created_messages,
        "marked_overdue": overdue,
    }


@router.post("/commitments/{commitment_id}/acknowledge", response_model=CommitmentOut)
async def acknowledge_commitment(
    commitment_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> CommitmentOut:
    commitment = await session.get(Commitment, commitment_id)
    if commitment is None or commitment.organization_id != ctx.organization_id:
        raise NotFoundError("Commitment not found.")
    commitment.acknowledged = True
    await session.commit()
    return CommitmentOut.model_validate(commitment)