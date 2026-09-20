"""Domain enumerations shared across models and services."""

from __future__ import annotations

import enum


class SourceType(str, enum.Enum):
    """External system a record originates from."""

    OUTLOOK = "outlook"
    TEAMS = "teams"
    GOODDAY = "goodday"
    MYWORK = "mywork"  # internally generated (insights, commitments)


class IntegrationStatus(str, enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    EXPIRED = "expired"


class Priority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class EventType(str, enum.Enum):
    EMAIL = "email"
    CALENDAR_EVENT = "calendar_event"
    TEAMS_MESSAGE = "teams_message"
    TASK = "task"
    INSIGHT = "insight"
    COMMITMENT = "commitment"
    REMINDER = "reminder"
    ACTIVITY = "activity"


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class AgentRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ActionStatus(str, enum.Enum):
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"


class ActionKind(str, enum.Enum):
    """Whether an action reads data or produces an external side effect."""

    READ = "read"
    WRITE = "write"


class ToolRisk(str, enum.Enum):
    """Risk level used by the approval policy."""

    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class CommitmentStatus(str, enum.Enum):
    OPEN = "open"
    FULFILLED = "fulfilled"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class CommitmentDirection(str, enum.Enum):
    """Who owes whom."""

    I_OWE = "i_owe"          # user promised someone else
    OWED_TO_ME = "owed_to_me"  # someone promised the user


class MemoryKind(str, enum.Enum):
    """Kinds of memory kept for the agent."""

    FACT = "fact"               # durable structured fact
    SEMANTIC = "semantic"       # embedded summary / note
    RELATIONSHIP = "relationship"  # links between people/projects
    PREFERENCE = "preference"   # user preferences


class SyncStatus(str, enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"