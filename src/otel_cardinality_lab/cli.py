from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .core import SEVERITY_ORDER, analyze_payload, load_budget, load_metrics, render_markdown


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.command == "analyze":
        return _analyze(args)
    parser.print_help()
    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="otel-cardinality-lab",
        description="Preflight OpenTelemetry metric cardinality budgets.",
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser("analyze", help="analyze an OTLP metrics JSON export")
    analyze.add_argument("input", help="path to OTLP metrics JSON or simple metrics JSON")
    analyze.add_argument("--budget", help="path to a JSON budget policy")
    analyze.add_argument("--output", help="write JSON report to this path")
    analyze.add_argument("--markdown", help="write Markdown report to this path")
    analyze.add_argument(
        "--fail-on",
        choices=["none", "low", "medium", "high", "critical"],
        default="none",
        help="exit non-zero when this severity or higher is present",
    )
    return parser


def _analyze(args: argparse.Namespace) -> int:
    payload = load_metrics(args.input)
    budget = load_budget(args.budget)
    report = analyze_payload(payload, budget)

    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)

    if args.markdown:
        Path(args.markdown).write_text(render_markdown(report), encoding="utf-8")

    threshold = args.fail_on
    highest = report["summary"]["highest_severity"]
    if threshold != "none" and SEVERITY_ORDER[highest] >= SEVERITY_ORDER[threshold]:
        print(f"otel-cardinality-lab: {highest} severity meets --fail-on {threshold}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
