"""Spawn the target MCP server and forward one tool invocation to it."""

from __future__ import annotations

import json
import os
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


async def invoke_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    target: list[str] | None = None,
    request_timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Open a session to the target MCP server, call ``name``, and return the payload."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command = target or target_command()
    server_params = StdioServerParameters(command=command[0], args=command[1:])

    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(name, arguments, request_timeout_s)
        texts = [
            block.text
            for block in (result.content or [])
            if getattr(block, "type", "") == "text" and hasattr(block, "text")
        ]
        payload: dict[str, Any] = {
            "tool": name,
            "isError": bool(result.isError),
            "content": texts,
        }
        if result.structuredContent is not None:
            payload["structured"] = result.structuredContent
        return payload
