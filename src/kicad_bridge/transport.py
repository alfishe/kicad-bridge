"""Spawn the target MCP server and forward tool invocations to it.

The default :class:`TargetSession` keeps one persistent stdio connection to the
target server (spawned lazily on first call) instead of paying process startup
per invocation.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from dataclasses import dataclass, field
from typing import Any

DEFAULT_TARGET = ["kicad-mcp-pro"]

DESTRUCTIVE_PREFIXES = ("delete", "remove", "sch_delete", "pcb_delete")


def target_command() -> list[str]:
    override = os.environ.get("KICAD_BRIDGE_TARGET")
    if override:
        parsed = json.loads(override)
        if isinstance(parsed, list):
            return [str(part) for part in parsed]
    return list(DEFAULT_TARGET)


def requires_confirmation(name: str) -> bool:
    casefold = name.casefold()
    return casefold.startswith(DESTRUCTIVE_PREFIXES)


@dataclass
class TargetSession:
    """Persistent stdio MCP session to one target server process."""

    command: list[str] = field(default_factory=target_command)
    request_timeout_s: float = 120.0
    passthrough_env: bool = True
    _stack: contextlib.AsyncExitStack | None = None
    _session: Any = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def running(self) -> bool:
        return self._session is not None

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_started()
            result = await self._session.call_tool(name, arguments, self.request_timeout_s)

        texts = [
            block.text
            for block in (result.content or [])
            if getattr(block, "type", "") == "text" and hasattr(block, "text")
        ]
        is_error = getattr(result, "is_error", getattr(result, "isError", False))
        structured = getattr(result, "structured_content", None)
        if structured is None:
            structured = getattr(result, "structuredContent", None)
        payload: dict[str, Any] = {
            "tool": name,
            "isError": bool(is_error),
            "content": texts,
        }
        if structured is not None:
            payload["structured"] = structured
        return payload

    async def _ensure_started(self) -> None:
        if self._session is not None:
            return

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        command = self.command or target_command()
        # mcp's stdio_client filters env to a safe whitelist by default, which
        # strips KICAD_MCP_* config — pass the full environment unless disabled.
        env = {**os.environ} if self.passthrough_env else None
        server_params = StdioServerParameters(
            command=command[0], args=command[1:], env=env
        )

        stack = contextlib.AsyncExitStack()
        read, write = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        self._stack = stack
        self._session = session

    async def stop(self) -> None:
        stack, self._stack, self._session = self._stack, None, None
        if stack is not None:
            with contextlib.suppress(Exception):
                await stack.aclose()


_session: TargetSession | None = None
_session_lock = asyncio.Lock()


async def get_target_session() -> TargetSession:
    global _session
    async with _session_lock:
        if _session is None:
            _session = TargetSession()
        return _session


async def restart_target_session() -> TargetSession:
    global _session
    async with _session_lock:
        if _session is not None:
            await _session.stop()
        _session = TargetSession()
        return _session


async def invoke_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    target: list[str] | None = None,
    request_timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Invoke via the persistent session; ``target`` forces a fresh one-shot session."""
    if target is not None:
        one_shot = TargetSession(command=list(target), request_timeout_s=request_timeout_s)
        try:
            return await one_shot.call(name, arguments)
        finally:
            await one_shot.stop()
    session = await get_target_session()
    session.request_timeout_s = request_timeout_s
    return await session.call(name, arguments)
