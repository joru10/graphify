"""Safe, deterministic Graphify integration for a Second Brain vault.

This module deliberately builds a relationship graph from compiled Markdown
only. It does not invoke an LLM, read raw evidence by default, or write back
to the knowledge base. The resulting graph is a derived read surface for
agents; Second Brain remains the source of truth.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CONFIG_VERSION = 1
DEFAULT_SCOPE = "compiled"
DEFAULT_OUTPUT_DIR = Path("graph/graphify/compiled")
DEFAULT_INCLUDE = ["wiki", "spaces", "system"]
DEFAULT_EXTENSIONS = [".md", ".mdx", ".qmd", ".markdown", ".txt"]
DEFAULT_EXCLUDES = [
    "raw",
    "_Import",
    "assets",
    "graph",
    ".git",
    ".obsidian",
    ".trash",
    "node_modules",
    ".venv",
    "__pycache__",
    ".cache",
    "cache",
]
DEFAULT_SECRET_FILENAME_PATTERNS = [
    ".env",
    ".env.*",
    "*secret*",
    "*credential*",
    "*token*",
    "*password*",
    "*apikey*",
    "*api_key*",
    "*private-key*",
    "*private_key*",
]
DEFAULT_MAX_FILES = 25_000
DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024
DEFAULT_VIZ_NODE_LIMIT = 10_000
DEFAULT_COMMUNITY_FALLBACK_NODE_LIMIT = 10_000
DEFAULT_QUESTION_ANALYSIS_NODE_LIMIT = 10_000


class SecondBrainError(RuntimeError):
    """A user-actionable Second Brain integration error."""


@dataclass(frozen=True)
class SourceInfo:
    path: Path
    relative_path: str
    sha256: str
    size: int
    word_count: int


def default_config(root: Path) -> dict[str, Any]:
    """Return the privacy-first default policy for a Second Brain vault."""
    return {
        "schema_version": CONFIG_VERSION,
        "scope": DEFAULT_SCOPE,
        "include": list(DEFAULT_INCLUDE),
        "extensions": list(DEFAULT_EXTENSIONS),
        "exclude": list(DEFAULT_EXCLUDES),
        "secret_filename_patterns": list(DEFAULT_SECRET_FILENAME_PATTERNS),
        "output_dir": DEFAULT_OUTPUT_DIR.as_posix(),
        "max_files": DEFAULT_MAX_FILES,
        "max_file_bytes": DEFAULT_MAX_FILE_BYTES,
        "semantic_extraction": False,
        "policy": {
            "source_of_truth": "Second Brain vault",
            "derived_surface": "Graphify relationship graph",
            "raw_evidence_indexed": False,
            "external_model_calls": False,
            "agent_writes_to_graph": False,
        },
        "notes": [
            "compiled scope indexes wiki, spaces, and system Markdown only",
            "raw, _Import, assets, graph, caches, and secret-shaped filenames are excluded",
            "expand scope only through an explicit policy review",
        ],
    }


def _candidate_roots() -> list[Path]:
    candidates: list[Path] = []
    env_root = os.environ.get("SECOND_BRAIN_ROOT", "").strip()
    if env_root:
        candidates.append(Path(env_root).expanduser())

    cwd = Path.cwd()
    if (cwd / "wiki").is_dir() and (cwd / "system").is_dir():
        candidates.append(cwd)

    candidates.extend(
        [
            Path.home() / "Documents" / "Second Brain",
            Path("/opt/second-brain"),
            Path("/home/node/Applications/second-brain"),
        ]
    )

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.expanduser().resolve())
        except (OSError, RuntimeError):
            key = str(candidate.expanduser())
        if key not in seen:
            seen.add(key)
            unique.append(candidate.expanduser())
    return unique


def resolve_root(root: str | Path | None = None) -> Path:
    """Resolve an explicit or local/container Second Brain root."""
    if root is not None:
        candidate = Path(root).expanduser()
        if not candidate.is_dir():
            raise SecondBrainError(f"Second Brain root not found or not a directory: {candidate}")
        return candidate.resolve()

    for candidate in _candidate_roots():
        if candidate.is_dir():
            return candidate.resolve()
    searched = ", ".join(str(p) for p in _candidate_roots())
    raise SecondBrainError(f"Second Brain root not found. Searched: {searched}")


def config_path(root: Path, configured: str | Path | None = None) -> Path:
    if configured is None:
        return root / "system" / "graphify" / "config.json"
    configured_path = Path(configured).expanduser()
    return configured_path if configured_path.is_absolute() else root / configured_path


def load_config(root: Path, configured: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    """Load and validate a policy config, falling back to safe defaults."""
    path = config_path(root, configured)
    if not path.exists():
        return path, default_config(root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SecondBrainError(f"Cannot read Graphify policy config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SecondBrainError(f"Graphify policy config must be a JSON object: {path}")

    merged = default_config(root)
    merged.update(raw)
    if merged.get("schema_version") != CONFIG_VERSION:
        raise SecondBrainError(
            f"Unsupported Graphify policy schema {merged.get('schema_version')!r}; "
            f"expected {CONFIG_VERSION}: {path}"
        )
    if merged.get("scope", DEFAULT_SCOPE) != DEFAULT_SCOPE:
        raise SecondBrainError(
            f"Unsupported Second Brain scope {merged.get('scope')!r}; only 'compiled' is enabled"
        )
    if merged.get("semantic_extraction"):
        raise SecondBrainError(
            "semantic_extraction is disabled for the shared agent graph; use an explicit, "
            "reviewed Graphify semantic workflow instead"
        )
    for key in ("include", "exclude", "extensions", "secret_filename_patterns"):
        if not isinstance(merged.get(key), list) or not all(
            isinstance(value, str) and value.strip() for value in merged[key]
        ):
            raise SecondBrainError(f"Graphify policy field '{key}' must be a non-empty string list")
    for key, default in (("max_files", DEFAULT_MAX_FILES), ("max_file_bytes", DEFAULT_MAX_FILE_BYTES)):
        try:
            value = int(merged.get(key, default))
        except (TypeError, ValueError) as exc:
            raise SecondBrainError(f"Graphify policy field '{key}' must be an integer") from exc
        if value <= 0:
            raise SecondBrainError(f"Graphify policy field '{key}' must be positive")
        merged[key] = value
    output = merged.get("output_dir")
    if not isinstance(output, str) or not output.strip():
        raise SecondBrainError("Graphify policy field 'output_dir' must be a relative path")
    return path, merged


def write_config(root: Path, configured: str | Path | None = None, *, force: bool = False) -> Path:
    """Create the default policy without overwriting an existing policy."""
    path = config_path(root, configured)
    if path.exists() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, default_config(root))
    return path


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError, RuntimeError) as exc:
        raise SecondBrainError(f"Path is outside the Second Brain root: {path}") from exc


def _output_dir(root: Path, policy: dict[str, Any]) -> Path:
    raw = Path(str(policy["output_dir"])).expanduser()
    if raw.is_absolute():
        candidate = raw
    else:
        candidate = root / raw
    try:
        candidate.resolve().relative_to(root.resolve())
    except (ValueError, OSError, RuntimeError) as exc:
        raise SecondBrainError("Graphify output_dir must stay inside the Second Brain root") from exc
    return candidate


def _is_excluded(relative_path: str, patterns: Iterable[str]) -> bool:
    normalized = relative_path.strip("/")
    parts = normalized.split("/") if normalized else []
    lower_path = normalized.lower()
    lower_parts = {part.lower() for part in parts}
    for pattern in patterns:
        clean = pattern.strip().strip("/")
        if not clean:
            continue
        lower = clean.lower()
        if lower in lower_parts or lower_path == lower or lower_path.startswith(lower + "/"):
            return True
        if fnmatch.fnmatchcase(lower_path, lower):
            return True
    return False


def _is_secret_filename(name: str, patterns: Iterable[str]) -> bool:
    lower = name.lower()
    return any(fnmatch.fnmatchcase(lower, pattern.lower()) for pattern in patterns)


def _walk_include(root: Path, include: str, *, excludes: list[str], secret_patterns: list[str], extensions: set[str]) -> list[Path]:
    candidate = root / include
    if not candidate.exists():
        return []
    if candidate.is_symlink():
        return []
    if candidate.is_file():
        rel = _relative_path(root, candidate)
        if (
            candidate.suffix.lower() in extensions
            and not _is_excluded(rel, excludes)
            and not _is_secret_filename(candidate.name, secret_patterns)
        ):
            return [candidate]
        return []
    if not candidate.is_dir():
        return []

    found: list[Path] = []
    for directory, dirnames, filenames in os.walk(candidate, topdown=True, followlinks=False):
        directory_path = Path(directory)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames, key=str.casefold):
            child = directory_path / dirname
            if child.is_symlink():
                continue
            rel_dir = _relative_path(root, child)
            if _is_excluded(rel_dir, excludes) or _is_secret_filename(dirname, secret_patterns):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames, key=str.casefold):
            path = directory_path / filename
            if path.is_symlink() or not path.is_file():
                continue
            rel = _relative_path(root, path)
            if _is_excluded(rel, excludes) or _is_secret_filename(filename, secret_patterns):
                continue
            if path.suffix.lower() in extensions:
                found.append(path)
    return found


def discover_sources(root: Path, policy: dict[str, Any]) -> list[SourceInfo]:
    """Discover, hash, and size-check the policy-approved source corpus."""
    extensions = {
        (value if value.startswith(".") else f".{value}").lower()
        for value in policy["extensions"]
    }
    excludes = list(policy["exclude"])
    output = _output_dir(root, policy)
    try:
        output_rel = _relative_path(root, output)
    except SecondBrainError:
        output_rel = ""
    if output_rel:
        excludes.append(output_rel)

    paths: dict[str, Path] = {}
    for include in policy["include"]:
        for path in _walk_include(
            root,
            include,
            excludes=excludes,
            secret_patterns=list(policy["secret_filename_patterns"]),
            extensions=extensions,
        ):
            paths[_relative_path(root, path)] = path

    ordered = sorted(paths.items(), key=lambda item: item[0].casefold())
    if len(ordered) > int(policy["max_files"]):
        raise SecondBrainError(
            f"Graphify scope contains {len(ordered):,} files, above the configured "
            f"limit of {int(policy['max_files']):,}; narrow the policy before indexing"
        )

    result: list[SourceInfo] = []
    for relative, path in ordered:
        try:
            size = path.stat().st_size
            if size > int(policy["max_file_bytes"]):
                raise SecondBrainError(
                    f"Source file exceeds the configured size limit ({int(policy['max_file_bytes']):,} bytes): {relative}"
                )
            digest = hashlib.sha256()
            word_count = 0
            with path.open("rb") as handle:
                data = handle.read()
            digest.update(data)
            word_count = len(data.decode("utf-8", errors="replace").split())
        except SecondBrainError:
            raise
        except OSError as exc:
            raise SecondBrainError(f"Cannot read indexed source {relative}: {exc}") from exc
        result.append(SourceInfo(path, relative, digest.hexdigest(), size, word_count))
    return result


def _snapshot(sources: list[SourceInfo]) -> str:
    digest = hashlib.sha256()
    for source in sources:
        digest.update(source.relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.sha256.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    from graphify.paths import write_json_atomic

    write_json_atomic(path, value, indent=2, ensure_ascii=False)


def _write_text(path: Path, value: str) -> None:
    from graphify.paths import write_text_atomic

    write_text_atomic(path, value)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _accelerated_clustering_available() -> bool:
    """Return whether Graphify can avoid NetworkX Louvain on large graphs."""
    import importlib.util

    for module_name in ("graspologic_native", "graspologic"):
        try:
            if importlib.util.find_spec(module_name) is not None:
                return True
        except (ImportError, ModuleNotFoundError, ValueError):
            continue
    return False


def _connected_component_communities(graph: Any) -> dict[int, list[str]]:
    """Build bounded, deterministic communities without a clustering backend."""
    import networkx as nx

    undirected = graph.to_undirected(as_view=True) if graph.is_directed() else graph
    groups = [sorted(component, key=str) for component in nx.connected_components(undirected)]
    groups.sort(key=lambda nodes: (-len(nodes), tuple(map(str, nodes))))
    return {index: nodes for index, nodes in enumerate(groups)}


def _cluster_graph(graph: Any) -> tuple[dict[int, list[str]], str]:
    """Choose a safe community algorithm for the shared vault graph.

    A large Markdown vault can contain tens of thousands of nodes. NetworkX's
    Louvain fallback is correct but can take many minutes on that shape when
    the optional Leiden backend is absent. Connected components preserve the
    actual reachability boundary and finish in linear time, which is the safer
    default for the read-only agent index.
    """
    if (
        graph.number_of_nodes() >= DEFAULT_COMMUNITY_FALLBACK_NODE_LIMIT
        and not _accelerated_clustering_available()
    ):
        return _connected_component_communities(graph), "connected-components-fallback"
    from graphify.cluster import cluster

    return cluster(graph), "graphify-cluster"


def _normalize_extraction_edges(extraction: dict[str, Any], root: Path) -> int:
    """Repair resolvable Markdown targets and drop genuinely missing targets.

    Graphify preserves unresolved Markdown references in raw extraction output,
    but the validated graph schema requires every edge endpoint to be a node.
    A vault can legitimately contain a link to a note outside the selected
    scope, so those edges are omitted rather than inventing a node or leaking
    an absolute path into the shared graph.
    """
    nodes = extraction.get("nodes", [])
    edges = extraction.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return 0
    node_ids = {node.get("id") for node in nodes if isinstance(node, dict)}
    file_nodes: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict) or node.get("node_kind") != "page":
            continue
        source = node.get("source_file")
        node_id = node.get("id")
        if isinstance(source, str) and isinstance(node_id, str):
            file_nodes[source.casefold()] = node_id

    kept: list[dict[str, Any]] = []
    dropped = 0
    for edge in edges:
        if not isinstance(edge, dict):
            dropped += 1
            continue
        target = edge.get("target")
        target_file = edge.pop("target_file", None)
        if target not in node_ids and isinstance(target_file, str):
            try:
                relative = _relative_path(root, Path(target_file)).casefold()
            except SecondBrainError:
                relative = ""
            replacement = file_nodes.get(relative)
            if replacement is not None:
                edge["target"] = replacement
                target = replacement
        if edge.get("source") in node_ids and target in node_ids:
            kept.append(edge)
        else:
            dropped += 1
    extraction["edges"] = kept
    if "links" in extraction:
        extraction["links"] = kept
    return dropped


def _build_stage(
    root: Path,
    sources: list[SourceInfo],
    cache_dir: Path,
    stage: Path,
    *,
    no_viz: bool,
) -> dict[str, Any]:
    """Build all derived artifacts in an isolated directory."""
    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.build import build_from_json
    from graphify.cluster import score_all
    from graphify.extract import extract
    from graphify.export import to_json
    from graphify.report import generate
    from graphify.validate import assert_valid

    stage.mkdir(parents=True, exist_ok=False)
    cache_dir.mkdir(parents=True, exist_ok=True)
    extraction = extract(
        [source.path for source in sources],
        cache_root=cache_dir,
        root=root,
        parallel=True,
    )
    dropped_edges = _normalize_extraction_edges(extraction, root)
    if dropped_edges:
        print(
            f"warning: omitted {dropped_edges} reference edge(s) to notes outside the compiled scope",
            file=sys.stderr,
        )
    assert_valid(extraction)
    graph = build_from_json(extraction, root=root)
    communities, community_method = _cluster_graph(graph)
    cohesion = score_all(graph, communities)
    labels = {int(cid): f"Community {cid}" for cid in communities}
    gods = god_nodes(graph)
    surprises = surprising_connections(graph, communities)
    question_analysis_skipped = graph.number_of_nodes() > DEFAULT_QUESTION_ANALYSIS_NODE_LIMIT
    questions = [] if question_analysis_skipped else suggest_questions(graph, communities, labels)

    graph_path = stage / "graph.json"
    if not to_json(graph, communities, str(graph_path), force=True, community_labels=labels):
        raise SecondBrainError("Graphify refused to write the staged graph")

    detection = {
        "total_files": len(sources),
        "total_words": sum(source.word_count for source in sources),
    }
    report = generate(
        graph,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        {"input": 0, "output": 0},
        str(root),
        suggested_questions=questions,
        built_at_commit=None,
    )
    _write_text(stage / "GRAPH_REPORT.md", report)
    _write_json(
        stage / ".graphify_analysis.json",
        {
            "communities": {str(k): v for k, v in communities.items()},
            "cohesion": {str(k): v for k, v in cohesion.items()},
            "gods": gods,
            "surprises": surprises,
            "questions": questions,
            "question_analysis_skipped": question_analysis_skipped,
            "community_method": community_method,
            "extraction_mode": "deterministic-markdown",
        },
    )

    html_written = False
    if not no_viz:
        try:
            from graphify.export import to_html

            raw_limit = os.environ.get("GRAPHIFY_VIZ_NODE_LIMIT", str(DEFAULT_VIZ_NODE_LIMIT))
            viz_limit = int(raw_limit)
            if viz_limit <= 0:
                raise ValueError("GRAPHIFY_VIZ_NODE_LIMIT must be positive")
            # The HTML exporter recursively renders an aggregated community
            # graph using its environment default. Keep that recursive pass at
            # the same limit as the outer pass unless the caller set it.
            had_limit = "GRAPHIFY_VIZ_NODE_LIMIT" in os.environ
            if not had_limit:
                os.environ["GRAPHIFY_VIZ_NODE_LIMIT"] = str(viz_limit)
            try:
                html_written = bool(
                    to_html(
                        graph,
                        communities,
                        str(stage / "graph.html"),
                        community_labels=labels,
                        node_limit=viz_limit,
                    )
                )
            finally:
                if not had_limit:
                    os.environ.pop("GRAPHIFY_VIZ_NODE_LIMIT", None)
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"warning: Graphify HTML visualization was skipped: {exc}", file=sys.stderr)

    return {
        "source_count": len(sources),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "community_count": len(communities),
        "community_method": community_method,
        "question_analysis_skipped": question_analysis_skipped,
        "html_written": html_written,
        "unresolved_references_dropped": dropped_edges,
    }


def _promote(stage: Path, output: Path) -> None:
    """Promote a complete stage while retaining the previous graph on failure."""
    previous = output.parent / f".{output.name}.previous-{uuid.uuid4().hex}"
    moved_previous = False
    try:
        if output.exists() or output.is_symlink():
            os.replace(output, previous)
            moved_previous = True
        os.replace(stage, output)
    except BaseException:
        if moved_previous and not output.exists():
            os.replace(previous, output)
        raise
    finally:
        if previous.exists():
            shutil.rmtree(previous, ignore_errors=True)


def read_manifest(output: Path) -> dict[str, Any] | None:
    return _read_json(output / "manifest.json")


def status(
    root: str | Path | None = None,
    configured: str | Path | None = None,
    *,
    scan: bool = True,
) -> dict[str, Any]:
    resolved_root = resolve_root(root)
    policy_path, policy = load_config(resolved_root, configured)
    output = _output_dir(resolved_root, policy)
    graph_path = output / "graph.json"
    manifest = read_manifest(output)
    current_sources: list[SourceInfo] | None = None
    scan_error: str | None = None
    if scan:
        try:
            current_sources = discover_sources(resolved_root, policy)
        except SecondBrainError as exc:
            scan_error = str(exc)

    current_snapshot = _snapshot(current_sources) if current_sources is not None else None
    recorded_snapshot = manifest.get("source_snapshot") if manifest else None
    fresh = (
        None
        if current_sources is None
        else bool(graph_path.is_file() and manifest and current_snapshot == recorded_snapshot)
    )
    return {
        "root": str(resolved_root),
        "scope": policy.get("scope", DEFAULT_SCOPE),
        "config": str(policy_path),
        "output": str(output),
        "graph": str(graph_path),
        "graph_exists": graph_path.is_file(),
        "manifest_exists": manifest is not None,
        "fresh": fresh,
        "source_count": manifest.get("source_count") if manifest else None,
        "current_source_count": len(current_sources) if current_sources is not None else None,
        "node_count": manifest.get("node_count") if manifest else None,
        "edge_count": manifest.get("edge_count") if manifest else None,
        "community_count": manifest.get("community_count") if manifest else None,
        "community_method": manifest.get("community_method") if manifest else None,
        "unresolved_references_dropped": manifest.get("unresolved_references_dropped") if manifest else None,
        "built_at": manifest.get("built_at") if manifest else None,
        "graphify_version": manifest.get("graphify_version") if manifest else None,
        "extraction_mode": manifest.get("extraction_mode") if manifest else None,
        "semantic_extraction": bool(policy.get("semantic_extraction", False)),
        "scan_error": scan_error,
    }


def update(
    root: str | Path | None = None,
    configured: str | Path | None = None,
    *,
    force: bool = False,
    no_viz: bool = False,
) -> dict[str, Any]:
    """Refresh the shared graph and return a non-secret build summary."""
    resolved_root = resolve_root(root)
    policy_path, policy = load_config(resolved_root, configured)
    output = _output_dir(resolved_root, policy)
    sources = discover_sources(resolved_root, policy)
    source_snapshot = _snapshot(sources)
    existing = read_manifest(output)
    graph_path = output / "graph.json"
    if (
        not force
        and graph_path.is_file()
        and existing
        and existing.get("source_snapshot") == source_snapshot
    ):
        return status(resolved_root, policy_path, scan=False) | {
            "updated": False,
            "reason": "up-to-date",
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = output.parent / ".cache" / str(policy.get("scope", DEFAULT_SCOPE))
    stage = output.parent / f".{output.name}.staging-{os.getpid()}-{uuid.uuid4().hex}"
    try:
        build_summary = _build_stage(
            resolved_root,
            sources,
            cache_dir,
            stage,
            no_viz=no_viz,
        )
        artifacts = [
            name
            for name in (
                "graph.json",
                "GRAPH_REPORT.md",
                ".graphify_analysis.json",
                "graph.html",
            )
            if (stage / name).exists()
        ]
        try:
            from importlib.metadata import version

            graphify_version = version("graphifyy")
        except Exception:
            graphify_version = "unknown"
        manifest = {
            "schema_version": CONFIG_VERSION,
            "scope": policy.get("scope", DEFAULT_SCOPE),
            "root_label": resolved_root.name,
            "config": _relative_path(resolved_root, policy_path)
            if policy_path.is_relative_to(resolved_root)
            else str(policy_path),
            "source_snapshot": source_snapshot,
            "source_count": len(sources),
            "sources": [
                {
                    "path": source.relative_path,
                    "sha256": source.sha256,
                    "bytes": source.size,
                }
                for source in sources
            ],
            "node_count": build_summary["node_count"],
            "edge_count": build_summary["edge_count"],
            "community_count": build_summary["community_count"],
            "community_method": build_summary["community_method"],
            "question_analysis_skipped": build_summary["question_analysis_skipped"],
            "unresolved_references_dropped": build_summary["unresolved_references_dropped"],
            "artifacts": artifacts,
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "graphify_version": graphify_version,
            "extraction_mode": "deterministic-markdown",
            "semantic_extraction": False,
            "external_model_calls": False,
            "raw_evidence_indexed": False,
            "policy": policy.get("policy", {}),
        }
        _write_json(stage / "manifest.json", manifest)
        _promote(stage, output)
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        raise

    return {
        "root": str(resolved_root),
        "scope": policy.get("scope", DEFAULT_SCOPE),
        "config": str(policy_path),
        "output": str(output),
        "graph": str(output / "graph.json"),
        "updated": True,
        "reason": "rebuilt",
        "source_count": len(sources),
        "node_count": build_summary["node_count"],
        "edge_count": build_summary["edge_count"],
        "community_count": build_summary["community_count"],
        "community_method": build_summary["community_method"],
        "unresolved_references_dropped": build_summary["unresolved_references_dropped"],
        "html_written": build_summary["html_written"],
        "built_at": manifest["built_at"],
        "graphify_version": manifest["graphify_version"],
        "extraction_mode": manifest["extraction_mode"],
    }


def _print_status(value: dict[str, Any]) -> None:
    print("Second Brain Graphify")
    print(f"  Root: {value['root']}")
    print(f"  Scope: {value['scope']}")
    if value["fresh"] is True:
        graph_state = "ready and current"
    elif value["fresh"] is False:
        graph_state = "missing or stale"
    else:
        graph_state = "ready (freshness not scanned)" if value["graph_exists"] else "missing"
    print(f"  Graph: {graph_state}")
    if value.get("source_count") is not None:
        print(f"  Sources: {value['source_count']} indexed")
    if value.get("current_source_count") is not None:
        print(f"  Current sources: {value['current_source_count']}")
    if value.get("node_count") is not None:
        print(f"  Graph: {value['node_count']} nodes, {value.get('edge_count', 0)} edges")
    if value.get("community_count") is not None:
        print(
            f"  Communities: {value['community_count']} "
            f"({value.get('community_method', 'unknown')})"
        )
    print(f"  MCP graph: {value['graph']}")
    print("  Extraction: deterministic Markdown, no external model calls")
    if value.get("scan_error"):
        print(f"  Scan warning: {value['scan_error']}", file=sys.stderr)


def serve_scope(
    root: str | Path | None = None,
    configured: str | Path | None = None,
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8080,
    api_key: str | None = None,
    path: str = "/mcp",
    stateless: bool = False,
) -> None:
    """Serve the current scope through Graphify MCP."""
    resolved_root = resolve_root(root)
    _, policy = load_config(resolved_root, configured)
    graph_path = _output_dir(resolved_root, policy) / "graph.json"
    if not graph_path.is_file():
        raise SecondBrainError(
            f"Graph is not built: {graph_path}. Run 'graphify second-brain update' first."
        )
    if transport == "http":
        from graphify.serve import serve_http

        serve_http(
            str(graph_path),
            host=host,
            port=port,
            api_key=api_key,
            path=path,
            stateless=stateless,
        )
    else:
        from graphify.serve import serve

        serve(str(graph_path))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graphify second-brain",
        description="Build and serve a safe, deterministic graph of a Second Brain vault.",
    )
    sub = parser.add_subparsers(dest="subcommand")

    def common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--root", help="Second Brain root (auto-detected when omitted)")
        command.add_argument("--config", help="policy JSON path (default: <root>/system/graphify/config.json)")

    init = sub.add_parser("init", help="write the default privacy-first policy")
    common(init)
    init.add_argument("--force", action="store_true", help="replace an existing policy")

    check = sub.add_parser("status", help="show graph freshness and policy state")
    common(check)
    check.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    check.add_argument("--no-scan", action="store_true", help="do not scan the source corpus")

    refresh = sub.add_parser("update", help="rebuild the shared graph when source files changed")
    common(refresh)
    refresh.add_argument("--force", action="store_true", help="rebuild even when the source snapshot is unchanged")
    refresh.add_argument("--no-viz", action="store_true", help="skip graph.html generation")
    refresh.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    serve = sub.add_parser("serve", help="serve the current graph through Graphify MCP")
    common(serve)
    serve.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--api-key", default=os.environ.get("GRAPHIFY_API_KEY"))
    serve.add_argument("--path", default="/mcp")
    serve.add_argument("--stateless", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if not args.subcommand:
        _parser().print_help()
        return
    try:
        if args.subcommand == "init":
            root = resolve_root(args.root)
            path = write_config(root, args.config, force=args.force)
            print(f"Graphify policy: {path}")
        elif args.subcommand == "status":
            value = status(args.root, args.config, scan=not args.no_scan)
            if args.json:
                print(json.dumps(value, indent=2, ensure_ascii=False))
            else:
                _print_status(value)
        elif args.subcommand == "update":
            value = update(args.root, args.config, force=args.force, no_viz=args.no_viz)
            if args.json:
                print(json.dumps(value, indent=2, ensure_ascii=False))
            elif value["updated"]:
                print(
                    f"Second Brain graph updated: {value['source_count']} sources, "
                    f"{value['node_count']} nodes, {value['edge_count']} edges."
                )
                print(f"  Output: {value['output']}")
            else:
                print(f"Second Brain graph already current: {value['graph']}")
        elif args.subcommand == "serve":
            serve_scope(
                args.root,
                args.config,
                transport=args.transport,
                host=args.host,
                port=args.port,
                api_key=args.api_key,
                path=args.path,
                stateless=args.stateless,
            )
    except (SecondBrainError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
