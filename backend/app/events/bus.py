"""In-process pub/sub event bus with optional Redis fan-out.

Backend services publish domain events (new email, agent status, approval
needed); SSE endpoints subscribe per organization and stream them to the
frontend so no page refresh is required.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator


@dataclass
class DomainEvent:
    kind: str
    organization_id: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_sse(self) -> str:
        payload = {"kind": self.kind, "data": self.data, "created_at": self.created_at}
        return f"event: {self.kind}\ndata: {json.dumps(payload, default=str)}\n\n"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[DomainEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, organization_id: str) -> asyncio.Queue[DomainEvent]:
        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers[organization_id].add(queue)
        return queue

    async def unsubscribe(self, organization_id: str, queue: asyncio.Queue[DomainEvent]) -> None:
        async with self._lock:
            self._subscribers[organization_id].discard(queue)
            if not self._subscribers[organization_id]:
                self._subscribers.pop(organization_id, None)

    async def publish(self, event: DomainEvent) -> None:
        for queue in list(self._subscribers.get(event.organization_id, set())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest to keep the stream live rather than blocking producers.
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except Exception:
                    pass

    async def stream(
        self, organization_id: str, *, heartbeat_seconds: int = 20
    ) -> AsyncIterator[str]:
        queue = await self.subscribe(organization_id)
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            await self.unsubscribe(organization_id, queue)


event_bus = EventBus()