"""Commitment and follow-up detection.

Scans normalized emails and Teams messages for promise/follow-up language and
records structured ``Commitment`` rows. Detection is heuristic (deterministic,
testable); it never performs external actions. Phrases such as "I'll send",
"can you deliver", "please send this by" are matched, and an owner + direction
are inferred from the message direction and participants.

External text is untrusted: we only *extract* candidate commitments and surface
them as suggestions for the user to acknowledge.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.enums import CommitmentDirection, CommitmentStatus, SourceType
from app.models.operations import Commitment
from app.models.work import Email, Message

logger = get_logger("app.services.commitments")

# "I'll send ...", "I will ...", "we'll deliver ...", "let me follow up"
_I_OWE_PATTERNS = [
    re.compile(r"\bI(?:'ll| will| shall| can| am going to)\b[^.\n]{0,60}", re.I),
    re.compile(r"\bwe(?:'ll| will)\b[^.\n]{0,60}", re.I),
    re.compile(r"\b(let me|i'll|i will)\b[^.\n]{0,40}\b(send|share|deliver|follow up|prepare)\b", re.I),
]

# "please send ... by", "can you deliver ...", "could you ..."
_OWED_TO_ME_PATTERNS = [
    re.compile(r"\b(please|could you|can you|would you|kindly)\b[^.\n]{0,60}\b(send|share|deliver|update|review|provide)\b", re.I),
]

_DEADLINE_PATTERN = re.compile(
    r"\b(by|before|due|deadline|no later than)\s+"
    r"(today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"end of (?:day|week|month)|next week|eod|eow|"
    r"\d{1,2}(?:st|nd|rd|th)?(?:\s+\w+)?|\d{4}-\d{2}-\d{2})\b",
    re.I,
)

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


@dataclass
class DetectedCommitment:
    direction: str
    text: str
    owner_email: str | None
    owner_name: str | None
    counterparty_email: str | None
    counterparty_name: str | None
    due_at: datetime | None
    confidence: float
    source: str
    source_external_id: str


def _parse_due(text: str, now: datetime) -> datetime | None:
    match = _DEADLINE_PATTERN.search(text)
    if not match:
        return None
    token = match.group(2).lower().strip()
    if token in ("today", "tonight", "eod", "end of day"):
        return now.replace(hour=18, minute=0, second=0, microsecond=0)
    if token == "tomorrow":
        target = now + timedelta(days=1)
        return target.replace(hour=18, minute=0, second=0, microsecond=0)
    if token in ("end of week", "eow"):
        days = (4 - now.weekday()) % 7
        target = now + timedelta(days=days or 7)
        return target.replace(hour=18, minute=0, second=0, microsecond=0)
    if token == "next week":
        return (now + timedelta(days=7)).replace(hour=9, minute=0, second=0, microsecond=0)
    if token in _WEEKDAYS:
        days = (_WEEKDAYS[token] - now.weekday()) % 7
        target = now + timedelta(days=days or 7)
        return target.replace(hour=18, minute=0, second=0, microsecond=0)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        try:
            return datetime.fromisoformat(token).replace(tzinfo=timezone.utc, hour=18)
        except ValueError:
            return None
    return None


def detect_in_text(
    text: str,
    *,
    sender_email: str = "",
    sender_name: str = "",
    direction_is_inbound: bool = True,
    source: str = SourceType.OUTLOOK.value,
    source_external_id: str = "",
    user_email: str = "",
    now: datetime | None = None,
) -> list[DetectedCommitment]:
    """Extract candidate commitments from a piece of text.

    Inbound (received) messages suggest things *owed to me* or that *I owe*
    (if the user is addressed). Outbound messages suggest things *I owe*.
    """
    now = now or datetime.now(timezone.utc)
    results: list[DetectedCommitment] = []
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    due = _parse_due(text or "", now)

    for sentence in sentences:
        clean = sentence.strip()
        if len(clean) < 8:
            continue
        owes_me = any(p.search(clean) for p in _OWED_TO_ME_PATTERNS)
        i_owe = any(p.search(clean) for p in _I_OWE_PATTERNS)

        if owes_me and direction_is_inbound:
            results.append(
                DetectedCommitment(
                    direction=CommitmentDirection.OWED_TO_ME.value,
                    text=clean[:500],
                    owner_email=sender_email,
                    owner_name=sender_name,
                    counterparty_email=user_email,
                    counterparty_name="Me",
                    due_at=due,
                    confidence=0.6,
                    source=source,
                    source_external_id=source_external_id,
                )
            )
        elif i_owe:
            # "I'll ..." in an outbound message = I owe it.
            if not direction_is_inbound:
                results.append(
                    DetectedCommitment(
                        direction=CommitmentDirection.I_OWE.value,
                        text=clean[:500],
                        owner_email=user_email,
                        owner_name="Me",
                        counterparty_email=sender_email,
                        counterparty_name=sender_name,
                        due_at=due,
                        confidence=0.6,
                        source=source,
                        source_external_id=source_external_id,
                    )
                )
            else:
                # Someone else promising the user something.
                results.append(
                    DetectedCommitment(
                        direction=CommitmentDirection.OWED_TO_ME.value,
                        text=clean[:500],
                        owner_email=sender_email,
                        owner_name=sender_name,
                        counterparty_email=user_email,
                        counterparty_name="Me",
                        due_at=due,
                        confidence=0.5,
                        source=source,
                        source_external_id=source_external_id,
                    )
                )
    return results[:3]


async def _exists(
    session: AsyncSession, *, organization_id: uuid.UUID, text: str
) -> bool:
    existing = await session.scalar(
        select(Commitment.id).where(
            Commitment.organization_id == organization_id, Commitment.text == text
        )
    )
    return existing is not None


async def scan_emails(
    session: AsyncSession, *, organization_id: uuid.UUID, user_email: str = "", limit: int = 40
) -> int:
    created = 0
    emails = list(
        await session.scalars(
            select(Email)
            .where(Email.organization_id == organization_id)
            .order_by(Email.received_at.desc())
            .limit(limit)
        )
    )
    for email in emails:
        text = f"{email.subject}. {email.body_preview}"
        for detected in detect_in_text(
            text,
            sender_email=email.sender_email,
            sender_name=email.sender_name,
            direction_is_inbound=True,
            source=SourceType.OUTLOOK.value,
            source_external_id=email.external_id,
            user_email=user_email,
        ):
            if await _exists(session, organization_id=organization_id, text=detected.text):
                continue
            session.add(
                Commitment(
                    organization_id=organization_id,
                    direction=detected.direction,
                    status=CommitmentStatus.OPEN.value,
                    text=detected.text,
                    owner_email=detected.owner_email,
                    owner_name=detected.owner_name,
                    counterparty_email=detected.counterparty_email,
                    counterparty_name=detected.counterparty_name,
                    due_at=detected.due_at,
                    confidence=detected.confidence,
                    source=detected.source,
                    source_external_id=detected.source_external_id,
                    source_ref=email.subject,
                    detected_by="heuristic",
                )
            )
            created += 1
    await session.flush()
    return created


async def scan_messages(
    session: AsyncSession, *, organization_id: uuid.UUID, user_email: str = "", limit: int = 40
) -> int:
    created = 0
    messages = list(
        await session.scalars(
            select(Message)
            .where(Message.organization_id == organization_id)
            .order_by(Message.sent_at.desc())
            .limit(limit)
        )
    )
    for message in messages:
        for detected in detect_in_text(
            message.body,
            sender_email=message.sender_email,
            sender_name=message.sender_name,
            direction_is_inbound=(message.direction == "inbound"),
            source=SourceType.TEAMS.value,
            source_external_id=message.external_id,
            user_email=user_email,
        ):
            if await _exists(session, organization_id=organization_id, text=detected.text):
                continue
            session.add(
                Commitment(
                    organization_id=organization_id,
                    direction=detected.direction,
                    status=CommitmentStatus.OPEN.value,
                    text=detected.text,
                    owner_email=detected.owner_email,
                    owner_name=detected.owner_name,
                    counterparty_email=detected.counterparty_email,
                    counterparty_name=detected.counterparty_name,
                    due_at=detected.due_at,
                    confidence=detected.confidence,
                    source=detected.source,
                    source_external_id=detected.source_external_id,
                    source_ref=message.conversation_name,
                    detected_by="heuristic",
                )
            )
            created += 1
    await session.flush()
    return created


async def refresh_overdue(session: AsyncSession, *, organization_id: uuid.UUID) -> int:
    """Mark open commitments past due as overdue."""
    now = datetime.now(timezone.utc)
    rows = list(
        await session.scalars(
            select(Commitment).where(
                Commitment.organization_id == organization_id,
                Commitment.status == CommitmentStatus.OPEN.value,
                Commitment.due_at.is_not(None),
                Commitment.due_at < now,
            )
        )
    )
    for row in rows:
        row.status = CommitmentStatus.OVERDUE.value
    await session.flush()
    return len(rows)