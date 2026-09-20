"""OpenRouter implementation of ``AIProvider``.

Streaming via SSE, tool calling, retries with backoff, timeouts, and token
usage accounting. The API key is read server-side only and never returned to
clients. The model is resolved from configuration (``OPENROUTER_MODEL``).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

import httpx

from app.ai.provider import (
    AIMessage,
    AIProvider,
    ChatResult,
    StreamChunk,
    ToolCall,
    ToolSchema,
)
from app.core.config import settings
from app.core.errors import AIProviderError, AITimeoutError
from app.core.logging import get_logger

logger = get_logger("app.ai.openrouter")


def _base_url() -> str:
    """Resolve the configured OpenRouter base URL (without trailing slash)."""
    base = (settings.openrouter_base_url or "https://openrouter.ai/api/v1").rstrip("/")
    return f"{base}/chat/completions"


def _message_to_payload(message: AIMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content or ""}
    if message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    if message.name:
        payload["name"] = message.name
    if message.tool_calls:
        payload["tool_calls"] = message.tool_calls
    return payload


def _tool_to_payload(tool: ToolSchema) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _accumulate_tool_calls(deltas: list[dict[str, Any]]) -> list[ToolCall]:
    """Merge OpenAI-style streamed tool_call deltas by index."""
    merged: dict[int, dict[str, Any]] = {}
    for delta in deltas:
        index = delta.get("index", 0)
        entry = merged.setdefault(index, {"id": "", "name": "", "arguments": ""})
        if delta.get("id"):
            entry["id"] = delta["id"]
        function = delta.get("function") or {}
        if function.get("name"):
            entry["name"] = function["name"]
        if function.get("arguments"):
            entry["arguments"] += function["arguments"]
    calls: list[ToolCall] = []
    for index in sorted(merged):
        entry = merged[index]
        try:
            arguments = json.loads(entry["arguments"]) if entry["arguments"] else {}
        except json.JSONDecodeError:
            arguments = {}
        calls.append(
            ToolCall(id=entry["id"] or f"call_{index}", name=entry["name"], arguments=arguments)
        )
    return calls


class OpenRouterProvider(AIProvider):
    name = "openrouter"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or settings.openrouter_api_key
        self._model = model or settings.openrouter_model
        self.model = self._model
        self._timeout = settings.ai_request_timeout_seconds
        self._max_retries = settings.ai_max_retries

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if settings.frontend_base_url:
            headers["HTTP-Referer"] = settings.frontend_base_url
        headers["X-Title"] = "MyWork AI"
        return headers

    def _build_body(
        self,
        messages: list[AIMessage],
        tools: list[ToolSchema] | None,
        temperature: float,
        max_tokens: int | None,
        *,
        stream: bool,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [_message_to_payload(m) for m in messages],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        if tools:
            body["tools"] = [_tool_to_payload(t) for t in tools]
            body["tool_choice"] = "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    def _ensure_configured(self) -> None:
        if not self._api_key:
            raise AIProviderError(
                "The AI provider is not configured. Set OPENROUTER_API_KEY."
            )

    async def stream_chat(
        self,
        *,
        messages: list[AIMessage],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        self._ensure_configured()
        body = self._build_body(messages, tools, temperature, max_tokens, stream=True)
        attempt = 0
        while True:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    async with client.stream(
                        "POST", _base_url(), headers=self._headers(), json=body
                    ) as resp:
                        if resp.status_code >= 400:
                            text = (await resp.aread()).decode("utf-8", "ignore")
                            raise AIProviderError(
                                f"AI provider error ({resp.status_code})."
                            ) if resp.status_code < 500 else AIProviderError(
                                "The AI provider is temporarily unavailable."
                            )
                        async for chunk in self._iter_sse(resp):
                            yield chunk
                        return
            except (httpx.TimeoutException,) as exc:
                raise AITimeoutError("The AI request timed out. Retry.") from exc
            except (httpx.HTTPError, AIProviderError) as exc:
                attempt += 1
                if attempt > self._max_retries:
                    if isinstance(exc, AIProviderError):
                        raise
                    raise AIProviderError(
                        "Could not reach the AI provider. Retry shortly."
                    ) from exc
                await asyncio.sleep(min(2 ** attempt * 0.5, 6))

    async def _iter_sse(self, resp: httpx.Response) -> AsyncIterator[StreamChunk]:
        buffer_tool_calls: list[dict[str, Any]] = []
        async for line in resp.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                if buffer_tool_calls:
                    yield StreamChunk(tool_calls=_accumulate_tool_calls(buffer_tool_calls))
                return
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue

            if payload.get("usage"):
                usage = payload["usage"]
                yield StreamChunk(
                    usage={
                        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                        "completion_tokens": int(usage.get("completion_tokens", 0)),
                        "total_tokens": int(usage.get("total_tokens", 0)),
                    }
                )

            for choice in payload.get("choices", []):
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    yield StreamChunk(content=delta["content"])
                if delta.get("tool_calls"):
                    buffer_tool_calls.extend(delta["tool_calls"])
                finish = choice.get("finish_reason")
                if finish:
                    if buffer_tool_calls:
                        yield StreamChunk(
                            tool_calls=_accumulate_tool_calls(buffer_tool_calls),
                            finish_reason=finish,
                        )
                        buffer_tool_calls = []
                    else:
                        yield StreamChunk(finish_reason=finish)

    async def complete(
        self,
        *,
        messages: list[AIMessage],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        self._ensure_configured()
        body = self._build_body(
            messages, tools, temperature, max_tokens, stream=False, json_mode=json_mode
        )
        attempt = 0
        while True:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(
                        _base_url(), headers=self._headers(), json=body
                    )
                    if resp.status_code >= 400:
                        raise AIProviderError(
                            "The AI provider rejected the request."
                        )
                    payload = resp.json()
                    return self._parse_result(payload)
            except httpx.TimeoutException as exc:
                raise AITimeoutError("The AI request timed out. Retry.") from exc
            except AIProviderError:
                raise
            except httpx.HTTPError as exc:
                attempt += 1
                if attempt > self._max_retries:
                    raise AIProviderError(
                        "Could not reach the AI provider. Retry shortly."
                    ) from exc
                await asyncio.sleep(min(2 ** attempt * 0.5, 6))

    @staticmethod
    def _parse_result(payload: dict[str, Any]) -> ChatResult:
        choices = payload.get("choices") or [{}]
        choice = choices[0]
        message = choice.get("message") or {}
        tool_calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(id=call.get("id", ""), name=function.get("name", ""), arguments=arguments)
            )
        usage = payload.get("usage") or {}
        return ChatResult(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            model=payload.get("model"),
            usage={
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
            },
        )