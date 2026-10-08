"""Tests for catalog search, hot lists, and the invoke gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_bridge import catalog, hotlists, transport
from kicad_bridge.server import invoke_impl
from kicad_bridge.server import mcp as bridge_mcp


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


def test_hot_list_returns_curated_tools() -> None:
    payload = hotlists.hot_list("verification")
    assert payload["use_case"] == "verification"
    assert any(t["name"] == "verify_board" for t in payload["tools"])


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


async def test_invoke_requires_confirmation_for_destructive() -> None:

    payload = await invoke_impl("sch_delete_symbol", {"reference": "R1"}, confirm=False)
    assert "confirmation_required" in payload


async def test_invoke_rejects_unknown_tool() -> None:

    payload = await invoke_impl("no_such_tool_xyz", {}, confirm=True)
    assert "unknown_tool" in payload


async def test_invoke_forwards_to_transport(monkeypatch: pytest.MonkeyPatch) -> None:

    seen: dict[str, object] = {}

    async def fake_invoke(name: str, args: dict, *, target=None, request_timeout_s=120.0):
        seen["name"] = name
        seen["args"] = args
        return {"tool": name, "isError": False, "content": ["ok"]}

    monkeypatch.setattr(transport, "invoke_tool", fake_invoke)
    payload = await invoke_impl("verify_board", {}, confirm=True)

    assert seen["name"] == "verify_board"
    assert '"isError": false' in payload


def test_registered_tools_are_the_three_facade_tools() -> None:
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        names = {tool.name for tool in loop.run_until_complete(bridge_mcp.list_tools())}
    finally:
        loop.close()
    assert names == {"tool_search", "hot_list", "tool_invoke"}


def test_target_command_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(
        "KICAD_BRIDGE_TARGET",
        '["uv", "run", "--project", "{}", "kicad-mcp-pro"]'.format(tmp_path),
    )
    command = transport.target_command()
    assert command[0] == "uv" and command[-1] == "kicad-mcp-pro"
