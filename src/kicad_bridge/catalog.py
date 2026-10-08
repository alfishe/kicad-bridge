"""Tool catalog: bundled snapshot of the kicad-alfishe tool surface + search."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

Catalog = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolEntry:
    name: str
    description: str
    category: str
    category_description: str
    requires_kicad_running: bool


def catalog_file() -> str:
    """Resolve the catalog JSON path: KICAD_BRIDGE_CATALOG or the bundled snapshot."""
    override = os.environ.get("KICAD_BRIDGE_CATALOG")
    if override:
        return override
    return str(resources.files("kicad_bridge").joinpath("catalog.json"))


@lru_cache(maxsize=4)
def load_catalog(path: str | None = None) -> Catalog:
    return json.loads(Path_read(path or catalog_file()))  # type: ignore[arg-type]


def Path_read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def all_tools(catalog: Catalog | None = None) -> list[ToolEntry]:
    cat = catalog if catalog is not None else load_catalog()
    entries: list[ToolEntry] = []
    for category, info in cat.get("categories", {}).items():
        for tool in info.get("tools", []):
            entries.append(
                ToolEntry(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    category=category,
                    category_description=info.get("description", ""),
                    requires_kicad_running=bool(tool.get("requires_kicad_running", False)),
                )
            )
    return entries


def search(query: str, *, limit: int = 10, catalog: Catalog | None = None) -> list[dict[str, Any]]:
    """Rank tools against ``query``: exact name hit > name substring > description hit.

    Pure substring scoring keeps the bridge dependency-free; upgrade path is a
    vector index over the same catalog without changing the tool contract.
    """
    query = query.strip().casefold()
    if not query:
        return []

    scored: list[tuple[int, ToolEntry]] = []
    for entry in all_tools(catalog):
        name = entry.name.casefold()
        desc = entry.description.casefold()
        category = entry.category.casefold()
        score = 0
        if query == name:
            score = 100
        elif name.startswith(query):
            score = 80
        elif query in name:
            score = 60
        if query in desc:
            score += 20
        if query in category:
            score += 10
        if score:
            scored.append((score, entry))

    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    return [
        {
            "name": entry.name,
            "category": entry.category,
            "description": entry.description,
            "requires_kicad_running": entry.requires_kicad_running,
            "score": score,
        }
        for score, entry in scored[: max(1, limit)]
    ]
