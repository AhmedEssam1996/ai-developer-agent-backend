"""Agent orchestrator: the streaming reasoning + tool loop.

Flow (matches the product spec)::

    User -> Gateway -> Intent -> Context -> Planner -> Tool selection ->
    Execute -> Observation -> Reason/Replan -> Final response

The orchestrator yields **event dicts** which the API serializes as SSE. It
never exposes hidden chain-of-thought: it emits concise status/tool events and
the final streamed Markdown answer only.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import executor as executor_mod
from app.agents import memory, planner
from app.agents.planner import Plan
from app.ai.provider import AIMessage, ToolSchema, get_provider
from app.core.errors import AINotConfiguredError, AppError
from app.core.logging import get_logger
from app.models.agent import AgentMessage, AgentRun
from app.models.enums import ActionStatus, AgentRole, AgentRunStatus
from app.services import audit, integration_service
from app.security.untrusted import scan_for_injection
from app.tools.base import ToolContext
from app.tools.registry import all_tool_schemas

logger = get_logger("app.agents.orchestrator")

MAX_TOOL_ROUNDS = 6
MAX_TOOL_CALLS = 12


@dataclass
class AgentRequest:
    organization_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_name: str
    timezone: str
    prompt: str


def _event(kind: str, **data: Any) -> dict[str, Any]:
    return {"event": kind, "data": data}


class AgentOrchestrator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self, request: AgentRequest) -> AsyncIterator[dict[str, Any]]:
        started = time.monotonic()
        run = AgentRun(
            organization_id=request.organization_id,
            user_id=request.user_id,
            status=AgentRunStatus.RUNNING.value,
            prompt=request.prompt,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(run)
        await self.session.flush()

        yield _event("run_started", run_id=str(run.id))

        try:
            async for event in self._run_inner(run, request, started):
                yield event
        except AppError as exc:
            await self._fail_run(run, exc.message)
            yield _event("error", code=exc.code, message=exc.message, retryable=True)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Agent run failed unexpectedly")
            await self._fail_run(run, "Agent run failed.")
            yield _event(
                "error",
                code="agent_error",
                message="Something went wrong while running the agent. Please retry.",
                retryable=True,
            )

    async def _run_inner(
        self, run: AgentRun, request: AgentRequest, started: float
    ) -> AsyncIterator[dict[str, Any]]:
        # 1. Context + plan
        yield _event("status", label="Understanding your request", phase="intent")
        context = await memory.build_working_context(
            self.session,
            organization_id=request.organization_id,
            user_email=request.user_email,
        )
        plan = planner.build_plan(request.prompt, context)
        run.intent = plan.intent
        await self.session.flush()
        yield _event("intent", intent=plan.intent)

        # 2. Build tool context (adapters resolved once)
        adapters = None
        try:
            adapters = await integration_service.resolve_adapters(
                self.session, organization_id=request.organization_id
            )
        except AppError as exc:
            # Keep going: local normalized data may still answer the question.
            yield _event("warning", message=exc.message)

        tool_ctx = ToolContext(
            session=self.session,
            organization_id=request.organization_id,
            user_id=request.user_id,
            user_email=request.user_email,
            user_name=request.user_name,
            adapters=adapters,
            timezone=request.timezone,
        )

        provider = get_provider()
        messages: list[AIMessage] = [
            AIMessage(role="system", content=plan.system_prompt),
            AIMessage(role="user", content=request.prompt),
        ]
        tool_schemas = self._select_tools(plan)
        tool_calls_made = 0
        final_text = ""

        # 3. Reasoning + tool loop
        for round_index in range(MAX_TOOL_ROUNDS):
            stream = provider.stream_chat(messages=messages, tools=tool_schemas)
            assistant_text = ""
            pending_tool_calls: list[Any] = []
            usage: dict[str, int] = {}

            async for chunk in stream:
                if chunk.content:
                    assistant_text += chunk.content
                    if not pending_tool_calls:
                        # Stream visible prose as it arrives.
                        yield _event("token", text=chunk.content)
                if chunk.tool_calls:
                    pending_tool_calls.extend(chunk.tool_calls)
                if chunk.usage:
                    usage = chunk.usage

            self._account_tokens(run, usage)

            if assistant_text.strip():
                await self._store_message(run, AgentRole.ASSISTANT, assistant_text)
                final_text = assistant_text

            if not pending_tool_calls:
                break

            # Record the assistant's tool-call turn for the model.
            messages.append(
                AIMessage(
                    role="assistant",
                    content=assistant_text,
                    tool_calls=[
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments),
                            },
                        }
                        for call in pending_tool_calls
                    ],
                )
            )

            for call in pending_tool_calls:
                if tool_calls_made >= MAX_TOOL_CALLS:
                    break
                tool_calls_made += 1
                run.tool_call_count = tool_calls_made
                await self.session.flush()

                tool = self._lookup_tool(call.name)
                if tool is None:
                    messages.append(
                        AIMessage(
                            role="tool",
                            tool_call_id=call.id,
                            name=call.name,
                            content="Unknown tool.",
                        )
                    )
                    continue

                injection = scan_for_injection(json.dumps(call.arguments))

                if tool.kind.value == "read":
                    yield _event(
                        "tool_started", name=call.name, kind="read",
                        label=self._label_for(call.name),
                    )
                    outcome = await executor_mod.execute_read_action(
                        self.session,
                        run_id=run.id,
                        ctx=tool_ctx,
                        tool_name=call.name,
                        arguments=call.arguments,
                        sequence=tool_calls_made,
                    )
                    yield _event(
                        "tool_finished",
                        name=call.name,
                        kind="read",
                        ok=outcome.ok,
                        summary=outcome.observation.splitlines()[1][:200]
                        if "\n" in outcome.observation
                        else outcome.observation[:200],
                    )
                    messages.append(
                        AIMessage(
                            role="tool",
                            tool_call_id=call.id,
                            name=call.name,
                            content=outcome.observation,
                        )
                    )
                else:
                    yield _event(
                        "status", label=f"Preparing action: {call.name}", phase="action"
                    )
                    outcome = await executor_mod.propose_write_action(
                        self.session,
                        run_id=run.id,
                        requested_by=request.user_id,
                        ctx=tool_ctx,
                        tool_name=call.name,
                        arguments=call.arguments,
                        injection_flagged=injection.is_suspicious,
                        sequence=tool_calls_made,
                    )
                    run.status = AgentRunStatus.AWAITING_APPROVAL.value
                    await self.session.flush()
                    yield _event(
                        "approval_required",
                        action_id=str(outcome.action_id),
                        tool_name=call.name,
                        preview=outcome.preview,
                        arguments=call.arguments,
                        flagged=injection.is_suspicious,
                    )
                    messages.append(
                        AIMessage(
                            role="tool",
                            tool_call_id=call.id,
                            name=call.name,
                            content=(
                                "This action requires the user's approval before it can run. "
                                "Do not claim it was executed."
                            ),
                        )
                    )

            # Continue the loop to let the model reflect on observations.

        # 4. Finalize
        latency_ms = int((time.monotonic() - started) * 1000)
        run.latency_ms = latency_ms
        run.finished_at = datetime.now(timezone.utc)
        if run.status != AgentRunStatus.AWAITING_APPROVAL.value:
            run.status = AgentRunStatus.COMPLETED.value
        run.model = provider.model
        run.provider = provider.name
        await self.session.flush()

        if not final_text:
            fallback = "I gathered your data but could not produce a full answer. Please retry."
            yield _event("token", text=fallback)

        await audit.record_audit(
            self.session,
            action="agent.run",
            organization_id=request.organization_id,
            user_id=request.user_id,
            target_type="agent_run",
            target_id=str(run.id),
            detail={"intent": run.intent, "tool_calls": tool_calls_made},
        )

        yield _event(
            "run_finished",
            run_id=str(run.id),
            status=run.status,
            latency_ms=latency_ms,
            tool_calls=tool_calls_made,
            total_tokens=run.total_tokens,
            model=run.model,
        )

    # --- helpers -------------------------------------------------------------

    def _select_tools(self, plan: Plan) -> list[ToolSchema]:
        schemas = all_tool_schemas()
        if not plan.tool_hints:
            return schemas
        # Always include write tools (they need to be discoverable); ordering
        # isn't significant to the model, so we simply return all schemas but
        # keep this helper for future filtering/allow-lists per org policy.
        return schemas

    def _lookup_tool(self, name: str):
        from app.tools import get_tool

        return get_tool(name)

    def _label_for(self, name: str) -> str:
        mapping = {
            "search_outlook_emails": "Searching Outlook",
            "get_email": "Reading email",
            "search_calendar": "Checking your calendar",
            "get_calendar_event": "Reading calendar event",
            "search_teams_messages": "Searching Teams",
            "get_teams_conversation": "Reading Teams conversation",
            "search_goodday_tasks": "Checking GoodDay tasks",
            "get_goodday_task": "Reading GoodDay task",
        }
        return mapping.get(name, f"Running {name}")

    def _account_tokens(self, run: AgentRun, usage: dict[str, int]) -> None:
        if not usage:
            return
        run.prompt_tokens += int(usage.get("prompt_tokens", 0))
        run.completion_tokens += int(usage.get("completion_tokens", 0))
        run.total_tokens += int(usage.get("total_tokens", 0)) or (
            int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0))
        )

    async def _store_message(self, run: AgentRun, role: AgentRole, content: str) -> None:
        message = AgentMessage(
            run_id=run.id,
            role=role.value,
            content=content,
            sequence=0,
        )
        self.session.add(message)
        await self.session.flush()

    async def _fail_run(self, run: AgentRun, message: str) -> None:
        run.status = AgentRunStatus.FAILED.value
        run.error = message[:500]
        run.finished_at = datetime.now(timezone.utc)
        await self.session.flush()


async def run_agent(
    session: AsyncSession, request: AgentRequest
) -> AsyncIterator[dict[str, Any]]:
    orchestrator = AgentOrchestrator(session)
    async for event in orchestrator.run(request):
        yield event