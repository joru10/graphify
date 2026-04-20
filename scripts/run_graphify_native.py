#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from graphify.detect import detect
from graphify.watch import _rebuild_code


def _write_notice_report(target: Path, detection: dict) -> None:
    out = target / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)

    code_n = len(detection.get("files", {}).get("code", []))
    doc_n = len(detection.get("files", {}).get("document", []))
    paper_n = len(detection.get("files", {}).get("paper", []))
    image_n = len(detection.get("files", {}).get("image", []))

    notice = (
        "# Graphify Report\n\n"
        "No code files were detected, so AST graph build was skipped.\n\n"
        "Detected files:\n"
        f"- code: {code_n}\n"
        f"- document: {doc_n}\n"
        f"- paper: {paper_n}\n"
        f"- image: {image_n}\n\n"
        "For non-code semantic extraction (docs/pdfs/images), run graphify from your AI assistant workflow.\n"
    )

    (out / "GRAPH_REPORT.md").write_text(notice, encoding="utf-8")
    (out / "detection_summary.json").write_text(json.dumps(detection, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Native Graphify runner for macOS app")
    parser.add_argument("target", help="Folder to process")
    parser.add_argument("--mode", choices=["full", "update"], default="full")
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise SystemExit(f"error: target directory not found: {target}")

    detection = detect(target)
    code_files = detection.get("files", {}).get("code", [])

    if not code_files:
        _write_notice_report(target, detection)
        print("No code files found. Wrote graphify-out/GRAPH_REPORT.md with detection summary.")
        return 0

    ok = _rebuild_code(target)
    if not ok:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
