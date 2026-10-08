"""Curated per-use-case tool subsets (hot lists)."""

from __future__ import annotations

from typing import Any

from .catalog import load_catalog

HOT_LISTS: dict[str, list[str]] = {
    "schematic_entry": [
        "kicad_set_project",
        "sch_add_component",
        "sch_add_wire",
        "sch_add_label",
        "sch_modify_property",
        "sch_delete_symbol",
        "verify_board",
    ],
    "pcb_layout": [
        "kicad_set_project",
        "pcb_place_component",
        "pcb_move_component",
        "pcb_route_trace",
        "pcb_add_zone",
        "refill_zones",
        "verify_board",
    ],
    "verification": [
        "verify_board",
        "run_drc",
        "run_erc",
        "kicad_get_project_info",
    ],
    "manufacturing": [
        "export_gerber",
        "export_drill",
        "export_manufacturing_package",
        "export_bom",
        "verify_board",
    ],
    "library": [
        "library_resolve",
        "sch_add_component",
        "verify_board",
    ],
}

UNKNOWN_USE_CASE = "unknown_use_case"


def hot_list(use_case: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the curated tool list for a use case, validated against the catalog."""
    cat = catalog if catalog is not None else load_catalog()
    known = {
        tool["name"]
        for info in cat.get("categories", {}).values()
        for tool in info.get("tools", [])
    }

    if use_case not in HOT_LISTS:
        return {
            "use_case": use_case,
            "status": UNKNOWN_USE_CASE,
            "available_use_cases": sorted(HOT_LISTS),
        }

    tools = HOT_LISTS[use_case]
    return {
        "use_case": use_case,
        "tools": [
            {
                "name": name,
                "in_catalog": name in known,
            }
            for name in tools
        ],
        "stale": [name for name in tools if name not in known],
    }
