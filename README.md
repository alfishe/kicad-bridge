# kicad-bridge

Minimalist **search + invoke** MCP facade over the [kicad-mcp-pro](https://github.com/alfishe/kicad-mcp-pro)
tool catalog (390 tools, 16 categories). The agent-facing surface is exactly three tools:

| Tool | Purpose |
|---|---|
| `tool_search(query, limit)` | ranked catalog search (name > description > category) |
| `hot_list(use_case)` | curated minimal tool list per use case: `schematic_entry`, `pcb_layout`, `verification`, `manufacturing`, `library` |
| `tool_invoke(name, arguments, confirm)` | forward one call to the target KiCad MCP server; destructive tools require `confirm=true` |

## Run

```bash
uv sync
uv run kicad-bridge            # stdio MCP server
```

Configuration (env):

- `KICAD_BRIDGE_TARGET` — JSON command to spawn the target server
  (default `["kicad-mcp-pro"]`)
- `KICAD_BRIDGE_CATALOG` — path to an alternative catalog.json

## Refresh the catalog

```bash
cd ../kicad-alfishe
uv run python - <<'PY'
import json
from kicad_mcp.tools.router import TOOL_CATEGORIES
from kicad_mcp.tools.metadata import get_tool_metadata
cat = {}
for cname, info in TOOL_CATEGORIES.items():
    tools = [{"name": n,
              "description": (getattr(get_tool_metadata(n), "description", "") or "") if get_tool_metadata(n) else "",
              "requires_kicad_running": bool(getattr(get_tool_metadata(n), "requires_kicad_running", False)) if get_tool_metadata(n) else False}
             for n in info["tools"]]
    cat[cname] = {"description": info["description"], "tools": tools}
json.dump({"source": "alfishe/kicad-mcp-pro", "categories": cat},
          open("../kicad-bridge/src/kicad_bridge/catalog.json", "w"), indent=1)
PY
```
