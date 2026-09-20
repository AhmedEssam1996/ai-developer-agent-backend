"""GoodDay task adapter — normalizes GoodDay payloads into internal DTOs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.integrations.base import (
    NormalizedProject,
    NormalizedTask,
    TaskAdapter,
)
from app.integrations.goodday.client import GoodDayClient

logger = get_logger("app.integrations.goodday.adapters")

# GoodDay status codes → internal status. Kept local to the integration.
_STATUS_MAP = {
    "open": "open",
    "new": "open",
    "in_progress": "in_progress",
    "inprogress": "in_progress",
    "working": "in_progress",
    "blocked": "blocked",
    "hold": "blocked",
    "completed": "done",
    "done": "done",
    "closed": "done",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}

_PRIORITY_MAP = {
    "low": "low",
    "normal": "normal",
    "medium": "normal",
    "high": "high",
    "urgent": "urgent",
    "critical": "urgent",
}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


class GoodDayTaskAdapter(TaskAdapter):
    provider = "goodday"

    def __init__(self, api_key: str | None = None) -> None:
        self._client = GoodDayClient(api_key)

    async def health(self) -> bool:
        return await self._client.health()

    async def list_projects(self) -> list[NormalizedProject]:
        data = await self._client.get("/projects", limit=100)
        items = _as_list(data, "projects")
        return [
            NormalizedProject(
                external_id=str(p.get("id", "")),
                name=p.get("name", "") or p.get("title", ""),
                description=p.get("description", "") or "",
            )
            for p in items
        ]

    async def list_tasks(
        self,
        *,
        project_external_id: str | None = None,
        search: str | None = None,
        top: int = 100,
    ) -> list[NormalizedTask]:
        params: dict[str, Any] = {"limit": top}
        if project_external_id:
            params["projectId"] = project_external_id
        if search:
            params["search"] = search
        data = await self._client.get("/tasks", **params)
        items = _as_list(data, "tasks")
        return [self._normalize(t) for t in items]

    async def get_task(self, external_id: str) -> NormalizedTask | None:
        try:
            data = await self._client.get(f"/tasks/{external_id}")
        except Exception:
            return None
        if isinstance(data, dict) and "task" in data:
            data = data["task"]
        return self._normalize(data)

    async def create_task(
        self,
        *,
        title: str,
        description: str = "",
        due_at: datetime | None = None,
        assignee_email: str | None = None,
        project_external_id: str | None = None,
        priority: str = "normal",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": title,
            "description": description,
            "priority": _to_goodday_priority(priority),
        }
        if due_at:
            payload["dueDate"] = due_at.astimezone(timezone.utc).isoformat()
        if assignee_email:
            payload["assignee"] = assignee_email
        if project_external_id:
            payload["projectId"] = project_external_id
        data = await self._client.post("/tasks", json=payload)
        if isinstance(data, dict) and "task" in data:
            data = data["task"]
        return {"status": "created", "id": data.get("id") if isinstance(data, dict) else None,
                "title": title}

    async def update_task(self, external_id: str, **fields: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if "title" in fields:
            payload["name"] = fields["title"]
        if "description" in fields:
            payload["description"] = fields["description"]
        if "status" in fields:
            payload["status"] = _to_goodday_status(fields["status"])
        if "priority" in fields:
            payload["priority"] = _to_goodday_priority(fields["priority"])
        if fields.get("due_at"):
            payload["dueDate"] = fields["due_at"].astimezone(timezone.utc).isoformat()
        data = await self._client.patch(f"/tasks/{external_id}", json=payload)
        return {"status": "updated", "id": external_id, "applied": payload}

    @staticmethod
    def _normalize(t: dict[str, Any]) -> NormalizedTask:
        raw_status = str(t.get("status", "open")).lower()
        raw_priority = str(t.get("priority", "normal")).lower()
        due = _parse_dt(t.get("dueDate") or t.get("due_date"))
        return NormalizedTask(
            external_id=str(t.get("id", "")),
            title=t.get("name", "") or t.get("title", "") or "",
            description=t.get("description", "") or "",
            status=_STATUS_MAP.get(raw_status, "open"),
            priority=_PRIORITY_MAP.get(raw_priority, "normal"),
            due_at=due,
            completed_at=_parse_dt(t.get("completedDate") or t.get("completed_at")),
            assignee_email=t.get("assigneeEmail") or t.get("assignee"),
            assignee_name=t.get("assigneeName"),
            project_external_id=str(t.get("projectId")) if t.get("projectId") else None,
            project_name=t.get("projectName"),
            progress=int(t.get("progress", 0) or 0),
            web_link=t.get("url") or t.get("webLink"),
            raw=t,
        )


def _as_list(data: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        value = data.get(key) or data.get("data") or data.get("items")
        if isinstance(value, list):
            return value
    return []


def _to_goodday_status(status: str) -> str:
    mapping = {"open": "open", "in_progress": "in_progress", "blocked": "blocked",
               "done": "completed", "cancelled": "cancelled"}
    return mapping.get(status, status)


def _to_goodday_priority(priority: str) -> str:
    mapping = {"low": "low", "normal": "normal", "high": "high", "urgent": "critical"}
    return mapping.get(priority, "normal")