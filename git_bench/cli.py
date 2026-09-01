"""Command-line entry point for ``git bench`` / ``git-bench``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import gitutils, runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-bench",
        description=(
            "Time a build/test command at each commit in a git revision "
            "range and log the wall-clock results locally."
        ),
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="run a command at every commit in a revision range",
    )
    run_parser.add_argument(
        "range",
        help="a git revision range, e.g. HEAD~5..HEAD or abc123..def456",
    )
    run_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="the command to time, e.g. -- pytest -q",
    )

    return parser


def _clean_command(raw: List[str]) -> List[str]:
    if raw and raw[0] == "--":
        raw = raw[1:]
    return raw


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.action == "run":
        command = _clean_command(args.command)
        if not command:
            parser.error("no command given; pass it after '--', e.g. run HEAD~3..HEAD -- pytest")

        def report(result):
            print(f"{result.sha[:12]}  {result.seconds:8.3f}s  {result.subject}")

        try:
            results = runner.run_range(
                Path.cwd(),
                args.range,
                command,
                on_result=report,
            )
        except (gitutils.GitError, ValueError) as exc:
            print(f"git-bench: {exc}", file=sys.stderr)
            return 1

        failures = [r for r in results if r.returncode != 0]
        if failures:
            print(
                f"git-bench: {len(failures)} of {len(results)} commits exited non-zero",
                file=sys.stderr,
            )
            return 1
        return 0

    parser.error(f"unknown action {args.action!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
