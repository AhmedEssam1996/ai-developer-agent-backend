"""Policy engine: decides whether a tool call may auto-run or needs approval.

READ tools auto-run. WRITE tools are approval-gated. Additionally, any write
whose target is derived from untrusted external content (flagged injection) is
forced to require approval even if it would otherwise be low-risk.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.tools.base import Tool, ToolKind, ToolRisk


@dataclass
class PolicyDecision:
    requires_approval: bool
    reason: str
    risk: str


# Tools that are inherently external side effects.
_ALWAYS_APPROVAL = {
    "send_email",
    "send_teams_message",
    "create_goodday_task",
    "update_goodday_task",
    "create_calendar_event",
}


def evaluate(tool: Tool, *, injection_flagged: bool = False) -> PolicyDecision:
    """Return the policy decision for invoking ``tool``."""
    if tool.kind is ToolKind.READ:
        return PolicyDecision(False, "Read-only tool.", ToolRisk.LOW.value)

    # WRITE
    if tool.name in _ALWAYS_APPROVAL:
        return PolicyDecision(
            True,
            "External side effect requires explicit approval.",
            tool.risk.value,
        )
    if injection_flagged:
        return PolicyDecision(
            True,
            "Untrusted input was flagged; approval is required before acting.",
            ToolRisk.HIGH.value,
        )
    # Drafts and other non-destructive writes still require approval by default.
    return PolicyDecision(True, "Write action requires approval.", tool.risk.value)