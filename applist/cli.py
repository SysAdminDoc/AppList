"""Headless CLI mode for AppList."""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import APP_NAME, APP_VERSION
from .constants import parse_include_sources
from .scanner import ApplicationScanner
from .exports import (
    write_txt_export,
    write_csv_export,
    write_markdown_export,
    write_json_export,
    write_winget_export,
    write_html_export,
    write_pip_requirements_export,
    write_choco_export,
    write_restore_bundle_export,
    diff_json_snapshots,
    write_diff_report,
)


def build_cli_parser() -> argparse.ArgumentParser:
    """Build the headless CLI parser."""
    parser = argparse.ArgumentParser(
        prog="AppList.py",
        description="Scan installed Windows applications and export an inventory without launching the GUI.",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--export",
        choices=["txt", "csv", "md", "markdown", "json", "winget", "html", "pip", "choco", "bundle"],
        help="Export format to write.",
    )
    group.add_argument(
        "--diff",
        nargs=2,
        metavar=("OLD_JSON", "NEW_JSON"),
        help="Diff two AppList JSON snapshots and report Added/Removed/VersionChanged.",
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output file path (required for --export, optional for --diff).",
    )
    parser.add_argument(
        "--include",
        default="all",
        help=(
            "Comma-separated sources to scan. Supported: all, desktop, registry, "
            "store, program_files, chocolatey, scoop, pip, winget."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing non-empty bundle folder.",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} v{APP_VERSION}")
    return parser


def run_cli(argv: List[str]) -> int:
    """Run AppList in headless CLI mode."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    # Handle diff mode
    if args.diff:
        old_path, new_path = args.diff
        try:
            diff = diff_json_snapshots(old_path, new_path)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Error reading snapshots: {e}", file=sys.stderr)
            return 1

        output_path = args.output
        if output_path:
            out = Path(output_path).expanduser()
            if out.suffix.lower() == ".json":
                with open(str(out), "w", encoding="utf-8") as f:
                    json.dump(diff, f, indent=2, ensure_ascii=False)
                print(f"Diff report (JSON) written to {out}")
            else:
                write_diff_report(diff, str(out))
                print(f"Diff report written to {out}")
        else:
            print(write_diff_report(diff))

        s = diff["summary"]
        print(f"+{s['added']} added, -{s['removed']} removed, ~{s['version_changed']} version changed")
        return 0

    # Handle export mode
    if not args.output:
        parser.error("--output is required for --export mode.")

    export_format = "markdown" if args.export == "md" else args.export

    try:
        include_sources = parse_include_sources(args.include)
    except ValueError as e:
        parser.error(str(e))

    if export_format == "winget":
        include_sources.add("winget")
    elif export_format == "pip":
        include_sources.add("pip")
    elif export_format == "choco":
        include_sources.add("chocolatey")
    elif export_format == "bundle":
        include_sources.update({"winget", "pip", "chocolatey"})

    output_path = Path(args.output).expanduser()
    if output_path.parent and str(output_path.parent) not in ("", "."):
        output_path.parent.mkdir(parents=True, exist_ok=True)

    def status(message: str):
        print(message, file=sys.stderr)

    scanner = ApplicationScanner(status_callback=status)
    apps = scanner.scan_all(include_sources=include_sources)
    diagnostics = scanner.scan_diagnostics
    reportable_diagnostics = [
        diagnostic for diagnostic in diagnostics
        if diagnostic.status in {"skipped", "warning", "failed"} or diagnostic.warnings
    ]
    if reportable_diagnostics:
        print("Scan diagnostics:", file=sys.stderr)
        for diagnostic in reportable_diagnostics:
            print(
                f"  {diagnostic.source}: {diagnostic.status}; "
                f"rows={diagnostic.row_count}; duration={diagnostic.duration_seconds:.3f}s",
                file=sys.stderr,
            )
            for warning in diagnostic.warnings:
                print(f"    Warning: {warning}", file=sys.stderr)

    writers = {
        "txt": write_txt_export,
        "csv": write_csv_export,
        "markdown": write_markdown_export,
        "json": write_json_export,
        "winget": write_winget_export,
        "html": write_html_export,
        "pip": write_pip_requirements_export,
        "choco": write_choco_export,
        "bundle": write_restore_bundle_export,
    }

    try:
        if export_format == "bundle":
            result = writers["bundle"](apps, str(output_path), diagnostics, overwrite=args.overwrite)
        elif export_format in {"txt", "markdown", "json", "html"}:
            result = writers[export_format](apps, str(output_path), diagnostics)
        else:
            result = writers[export_format](apps, str(output_path))
    except (OSError, csv.Error, TypeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    exported_count = result if isinstance(result, int) else len(apps)
    if isinstance(result, dict):
        exported_count = result.get("application_count", len(apps))
    print(f"Exported {exported_count} applications to {output_path}")
    return 0
