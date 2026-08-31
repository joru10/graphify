from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pytest

import graphify.second_brain as second_brain


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "Second Brain"
    _write(root / "wiki" / "alpha.md", "# Alpha\nSee [Beta](../spaces/beta.md).\n")
    _write(root / "spaces" / "beta.md", "# Beta\nSee [[Alpha]].\n")
    _write(root / "system" / "runbook.md", "# Runbook\n")
    _write(root / "raw" / "private.md", "# Private\n")
    _write(root / "wiki" / ".env", "OPENAI_API_KEY=not-indexed\n")
    return root


def test_discover_sources_applies_compiled_policy(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    policy = second_brain.default_config(root)

    sources = second_brain.discover_sources(root, policy)

    assert [source.relative_path for source in sources] == [
        "spaces/beta.md",
        "system/runbook.md",
        "wiki/alpha.md",
    ]


def test_update_writes_graph_and_manifest_without_semantic_extraction(tmp_path: Path) -> None:
    root = _vault(tmp_path)

    result = second_brain.update(root, no_viz=True)

    assert result["updated"] is True
    output = root / "graph" / "graphify" / "compiled"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    graph = json.loads((output / "graph.json").read_text(encoding="utf-8"))
    assert manifest["extraction_mode"] == "deterministic-markdown"
    assert manifest["external_model_calls"] is False
    assert manifest["raw_evidence_indexed"] is False
    assert manifest["community_method"] == "graphify-cluster"
    assert manifest["source_count"] == 3
    assert graph["nodes"]
    assert all(not str(node.get("source_file", "")).startswith("/") for node in graph["nodes"])

    current = second_brain.status(root)
    assert current["fresh"] is True
    assert second_brain.update(root, no_viz=True)["reason"] == "up-to-date"


def test_failed_refresh_keeps_last_good_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(tmp_path)
    second_brain.update(root, no_viz=True)
    output = root / "graph" / "graphify" / "compiled"
    before_graph = (output / "graph.json").read_bytes()
    before_manifest = (output / "manifest.json").read_bytes()
    _write(root / "wiki" / "alpha.md", "# Alpha\nChanged.\n")

    def fail_build(*args, **kwargs):
        raise RuntimeError("simulated extraction failure")

    monkeypatch.setattr(second_brain, "_build_stage", fail_build)
    with pytest.raises(RuntimeError, match="simulated extraction failure"):
        second_brain.update(root, no_viz=True)

    assert (output / "graph.json").read_bytes() == before_graph
    assert (output / "manifest.json").read_bytes() == before_manifest


def test_out_of_scope_reference_is_not_written_as_absolute_path(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    _write(root / "spaces" / "beta.md", "# Beta\nSee [[NotInScope]].\n")

    result = second_brain.update(root, no_viz=True)
    graph = json.loads((root / "graph" / "graphify" / "compiled" / "graph.json").read_text(encoding="utf-8"))

    assert result["updated"] is True
    assert all(not str(edge.get("target", "")).startswith("/") for edge in graph["links"])


def test_large_graph_without_accelerated_backend_uses_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = nx.DiGraph()
    graph.add_edges_from([("a", "b"), ("c", "d")])
    monkeypatch.setattr(second_brain, "DEFAULT_COMMUNITY_FALLBACK_NODE_LIMIT", 1)
    monkeypatch.setattr(second_brain, "_accelerated_clustering_available", lambda: False)

    communities, method = second_brain._cluster_graph(graph)

    assert method == "connected-components-fallback"
    assert list(communities.values()) == [["a", "b"], ["c", "d"]]
