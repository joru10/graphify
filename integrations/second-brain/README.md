# Second Brain Integration

This integration makes Graphify a shared, read-only relationship layer over a
Second Brain vault for OpenClaw, Hermes, and other MCP-capable agents.

## Architecture

```text
Second Brain (source of truth)
  wiki/ + spaces/ + selected system/ Markdown
        |
        | deterministic local extraction, no LLM/API call
        v
graph/graphify/compiled/
  graph.json              agent-facing MCP graph
  GRAPH_REPORT.md         human review report
  graph.html              optional visual view
  manifest.json           freshness and policy record
        |
        +--> OpenClaw MCP (stdio)
        +--> Hermes MCP (stdio)
        +--> other local MCP clients
```

The native Graphify app remains a human visualization surface. Agents use the
MCP server against the same `graph.json`, so they do not depend on opening a
folder or finding a generated report manually.

## Safety boundary

The default `compiled` policy excludes `raw/`, `_Import/`, `assets/`, graph
outputs, caches, and secret-shaped filenames. It also disables semantic
extraction. This prevents an unattended refresh from sending private
documents to a model or turning raw evidence into an agent-facing index.

For a large vault without Graphify's optional Leiden backend, the refresh uses
deterministic connected components rather than NetworkX Louvain. This keeps
the scheduled build bounded while preserving the actual reachability groups;
the selected method is recorded in `manifest.json`. The expensive
betweenness-based question heuristic is also skipped above 10,000 nodes.

Graphify is derived state. It does not write to Second Brain, GBrain, REM, or
RL. It can help those agents orient themselves, but promotion into memory or
decision records remains an explicit workflow.

## Runtime commands

The integration is exposed by the Graphify CLI:

```text
graphify second-brain init
graphify second-brain status
graphify second-brain update
graphify second-brain serve
```

The host refresh service calls `update` periodically. `update` is snapshot
aware and leaves the last good graph in place if extraction or export fails.

## MCP configuration

OpenClaw uses a stdio server entry whose graph path is mounted as
`/home/node/Applications/second-brain/graph/graphify/compiled/graph.json`:

```json
{
  "graphify-second-brain": {
    "command": "/usr/local/bin/graphify-mcp",
    "args": [
      "/home/node/Applications/second-brain/graph/graphify/compiled/graph.json"
    ],
    "timeout": 1200
  }
}
```

Hermes uses the same graph through its `/opt/second-brain` mount and runs the
server from its immutable virtual environment:

```yaml
mcp_servers:
  graphify-second-brain:
    command: /opt/hermes/.venv/bin/graphify-mcp
    args:
      - /opt/second-brain/graph/graphify/compiled/graph.json
    timeout: 1200
```

Both runtimes must include the Graphify `mcp` extra. No API key is required for
stdio MCP, and no network listener is opened.
