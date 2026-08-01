"""Command-line entry point: stepmania-song-validator <library-path>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .reporting import render_human, render_json
from .validator import validate_library


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stepmania-song-validator",
        description=(
            "Validate a StepMania/ITGmania song library before copying it to "
            "a Batocera Songs/ directory: chart integrity, duplicate "
            "detection, and Batocera song-discovery layout checks."
        ),
    )
    parser.add_argument(
        "library_path",
        type=Path,
        help="Path to the song library root (contains group folders, e.g. Songs/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report instead of the human-readable summary",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report = validate_library(args.library_path)

    if args.json:
        print(render_json(report))
    else:
        print(render_human(report))

    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
