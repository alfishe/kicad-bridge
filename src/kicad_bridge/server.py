"""kicad-bridge MCP server: tool_search + tool_invoke + hot_list over the catalog."""

from __future__ import annotations

import json
from typing import Any

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # official SDK layout
    from mcp.server.fastmcp import FastMCP

from . import catalog, hotlists
from .transport import (
    get_target_session,
    requires_confirmation,
    restart_target_session,
)

mcp = FastMCP("kicad-bridge")


@mcp.tool()
def tool_search(query: str, limit: int = 10) -> str:
    """Search the KiCad MCP Pro tool catalog by name, description, or category."""
    return json.dumps(catalog.search(query, limit=limit), indent=2)


@mcp.tool()
def hot_list(use_case: str) -> str:
    """Return the curated minimal tool list for a use case (schematic_entry, pcb_layout, verification, manufacturing, library)."""
    return json.dumps(hotlists.hot_list(use_case), indent=2)


async def invoke_impl(
    name: str, arguments: dict[str, Any] | None = None, confirm: bool = False
) -> str:
    known = {entry.name for entry in catalog.all_tools()}
    if name not in known:
        return json.dumps(
            {"error": "unknown_tool", "tool": name, "hint": "use tool_search"}, indent=2
        )
    if requires_confirmation(name) and not confirm:
        return json.dumps(
            {
                "error": "confirmation_required",
                "tool": name,
                "hint": "destructive tool: re-invoke with confirm=true",
            },
            indent=2,
        )

    try:
        payload = await (await get_target_session()).call(name, arguments or {})
    except Exception as exc:  # noqa: BLE001 - surfaced to the agent as JSON
        return json.dumps({"error": "invoke_failed", "tool": name, "detail": str(exc)}, indent=2)
    return json.dumps(payload, indent=2)


@mcp.tool()
async def session_status() -> str:
    """Show whether the target KiCad MCP server session is running."""
    session = await get_target_session()
    return json.dumps({"running": session.running, "command": session.command}, indent=2)


@mcp.tool()
async def session_restart() -> str:
    """Stop and respawn the target KiCad MCP server session (pick up new config)."""
    session = await restart_target_session()
    return json.dumps({"restarted": True, "running": session.running}, indent=2)


@mcp.tool()
async def tool_invoke(
    name: str, arguments: dict[str, Any] | None = None, confirm: bool = False
) -> str:
    """Invoke one catalog tool on the target KiCad MCP server.

    Destructive tools (delete/remove) require confirm=true.
    Use tool_search or hot_list first to resolve the name and arguments.
    """
    return await invoke_impl(name, arguments, confirm)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
