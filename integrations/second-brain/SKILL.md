# Graphify Second Brain

Use the `graphify-second-brain` MCP server as a derived relationship index for
the Second Brain vault. It is an orientation and verification aid, not a
source of truth.

## Operating rules

- Second Brain remains authoritative; verify important claims in the cited
  note before acting.
- The shared `compiled` scope indexes Markdown from `wiki/`, `spaces/`, and
  selected `system/` content only.
- `raw/`, `_Import/`, `assets/`, graph outputs, caches, and secret-shaped
  filenames are intentionally excluded.
- The server uses deterministic local extraction. It makes no model/API calls
  and has no write tools.
- Treat `INFERRED` and `AMBIGUOUS` relationships as review prompts, never as
  confirmed facts.
- Do not write to `graph/graphify/compiled/`; refresh is performed by the host
  integration service.
- Do not copy Graphify output into REM, RL, or GBrain automatically. Those
  layers have separate ownership and promotion rules.

## When to use it

Use Graphify before a broad file scan when the task involves relationships,
architecture, dependencies, provenance, or cross-domain context. Prefer the
MCP tools for:

- finding the path between two concepts or notes;
- checking which notes reference a component or decision;
- locating central hubs and weakly connected areas;
- testing whether a claim has an explicit evidence chain;
- identifying ambiguous or missing relationships before asking for more data.

After Graphify has oriented the task, read the relevant Second Brain notes and
preserve source/evidence distinctions in the answer.
