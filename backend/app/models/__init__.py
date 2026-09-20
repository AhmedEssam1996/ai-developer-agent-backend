"""ORM models.

Importing this package registers every model on ``Base.metadata`` — required
before running ``create_all`` or Alembic autogenerate.
"""

from app.models.agent import ActionApproval, AgentAction, AgentMessage, AgentRun
from app.models.enums import (
    ActionKind,
    ActionStatus,
    AgentRole,
    AgentRunStatus,
    CommitmentDirection,
    CommitmentStatus,
    EventType,
    IntegrationStatus,
    MemoryKind,
    MessageDirection,
    Priority,
    SourceType,
    SyncStatus,
    TaskStatus,
    ToolRisk,
)
from app.models.identity import Membership, Organization, User
from app.models.integrations import Integration, OAuthAccount
from app.models.operations import (
    ActivityEvent,
    AuditLog,
    Commitment,
    MemoryItem,
    SyncState,
)
from app.models.work import (
    CalendarEvent,
    Email,
    Message,
    Person,
    Project,
    Task,
)

__all__ = [
    # enums
    "ActionKind",
    "ActionStatus",
    "AgentRole",
    "AgentRunStatus",
    "CommitmentDirection",
    "CommitmentStatus",
    "EventType",
    "IntegrationStatus",
    "MemoryKind",
    "MessageDirection",
    "Priority",
    "SourceType",
    "SyncStatus",
    "TaskStatus",
    "ToolRisk",
    # identity
    "Membership",
    "Organization",
    "User",
    # integrations
    "Integration",
    "OAuthAccount",
    # work
    "CalendarEvent",
    "Email",
    "Message",
    "Person",
    "Project",
    "Task",
    # agent
    "ActionApproval",
    "AgentAction",
    "AgentMessage",
    "AgentRun",
    # operations
    "ActivityEvent",
    "AuditLog",
    "Commitment",
    "MemoryItem",
    "SyncState",
]