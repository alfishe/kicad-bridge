"""Tests for catalog search, hot lists, and the invoke facade."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from kicad_bridge import catalog, hotlists
from kicad_bridge.server import invoke_impl
from kicad_bridge.server import mcp as bridge_mcp

# --- catalog search ----------------------------------------------------------


def test_search_finds_by_name_substring() -> None:
    results = catalog.search("verify")
    assert results, "verify_board must be discoverable"
    assert results[0]["name"] == "verify_board"


def test_search_ranks_exact_name_first() -> None:
    results = catalog.search("export_gerber", limit=5)
    assert results[0]["name"] == "export_gerber"
    assert results[0]["score"] == 100


def test_search_empty_query_returns_empty() -> None:
    assert catalog.search("") == []


# --- hot lists ----------------------------------------------------------------


def test_hot_list_returns_curated_tools() -> None:
    payload = hotlists.hot_list("verification")
    assert payload["use_case"] == "verification"
    assert any(tool["name"] == "verify_board" for tool in payload["tools"])


def test_hot_list_reports_stale_entries() -> None:
    catalog_stub = {
        "categories": {
            "validation": {
                "description": "x",
                "tools": [{"name": "verify_board", "description": ""}],
            }
        }
    }
    payload = hotlists.hot_list("verification", catalog=catalog_stub)
    assert payload["stale"], "missing tools must be flagged as stale"


def test_hot_list_unknown_use_case_lists_available() -> None:
    payload = hotlists.hot_list("does_not_exist")
    assert payload["status"] == "unknown_use_case"
    assert "verification" in payload["available_use_cases"]


# --- invoke facade ------------------------------------------------------------


async def test_invoke_requires_confirmation_for_destructive() -> None:
    payload = await invoke_impl("sch_delete_symbol", {"reference": "R1"}, confirm=False)
    assert "confirmation_required" in payload


async def test_invoke_rejects_unknown_tool() -> None:
    payload = await invoke_impl("no_such_tool_xyz", {}, confirm=True)
    assert "unknown_tool" in payload


async def test_invoke_forwards_to_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    from kicad_bridge import server as server_module

    seen: dict[str, object] = {}

    class FakeSession:
        async def call(self, name: str, args: dict) -> dict:
            seen["name"] = name
            seen["args"] = args
            return {"tool": name, "isError": False, "content": ["ok"]}

    async def fake_get_target_session() -> FakeSession:
        return FakeSession()

    monkeypatch.setattr(server_module, "get_target_session", fake_get_target_session)
    payload = await invoke_impl("verify_board", {}, confirm=True)

    assert seen["name"] == "verify_board"
    assert '"isError": false' in payload


def test_target_command_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from kicad_bridge.transport import target_command

    monkeypatch.setenv(
        "KICAD_BRIDGE_TARGET",
        f'["uv", "run", "--project", "{tmp_path}", "kicad-mcp-pro"]',
    )
    command = target_command()
    assert command[0] == "uv" and command[-1] == "kicad-mcp-pro"


# --- facade surface -------------------------------------------------------------


def test_registered_tools_are_the_facade_surface() -> None:
    loop = asyncio.new_event_loop()
    try:
        names = {tool.name for tool in loop.run_until_complete(bridge_mcp.list_tools())}
    finally:
        loop.close()
    assert names == {
        "tool_search",
        "hot_list",
        "tool_invoke",
        "session_status",
        "session_restart",
    }


async def test_target_session_self_host_roundtrip() -> None:
    """The bridge can serve as its own target: spawn it, call tool_search, stop."""
    from kicad_bridge.transport import TargetSession

    session = TargetSession(command=[sys.executable, "-m", "kicad_bridge"])
    try:
        payload = await session.call("tool_search", {"query": "verify", "limit": 3})
        assert '"verify_board"' in payload["content"][0]
    finally:
        await session.stop()
    assert not session.running
