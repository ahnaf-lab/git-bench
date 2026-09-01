"""Command-line entry point for ``git bench`` / ``git-bench``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import gitutils, install, report, runner, storage


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

    report_parser = subparsers.add_parser(
        "report",
        help="render a sparkline and table for previously recorded runs",
    )
    report_parser.add_argument(
        "--command",
        dest="report_command",
        default=None,
        help="which recorded command to report on; required if more than one is stored",
    )

    bisect_parser = subparsers.add_parser(
        "bisect",
        help="binary-search a range for the first commit whose command exceeds a time threshold",
    )
    bisect_parser.add_argument(
        "range",
        help="a git revision range, e.g. HEAD~20..HEAD or abc123..def456",
    )
    bisect_parser.add_argument(
        "--threshold",
        type=float,
        required=True,
        help="seconds; report the first commit whose command takes longer than this",
    )

    check_parser = subparsers.add_parser(
        "check",
        help="fail if HEAD is slower than a baseline revision by more than a percent threshold",
    )
    check_parser.add_argument(
        "baseline",
        help="a git revision to compare HEAD against, e.g. main or HEAD~1",
    )
    check_parser.add_argument(
        "--max-regression",
        dest="max_regression",
        type=float,
        default=10.0,
        help="allowed percent slowdown vs the baseline before failing (default: 10.0)",
    )

    install_parser = subparsers.add_parser(
        "install",
        help="wire the 'git bench' alias and prepare the local results cache",
    )
    install_parser.add_argument(
        "--global",
        dest="global_scope",
        action="store_true",
        help="write the alias to the global git config instead of this repo's local config",
    )

    return parser


def _split_command(argv: List[str]) -> "tuple[List[str], List[str]]":
    """Split ``argv`` on the first ``--`` into (front, command).

    Everything after ``--`` is the command to time, taken verbatim; this is
    done before argparse ever sees it so the command's own flags are never
    mistaken for ``git-bench`` options, and so ``--threshold``/other options
    can appear in any order relative to ``--`` on the front side.
    """
    if "--" in argv:
        idx = argv.index("--")
        return argv[:idx], argv[idx + 1 :]
    return argv, []


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    front, command = _split_command(argv)
    parser = build_parser()
    args = parser.parse_args(front)

    if args.action == "run":
        if not command:
            parser.error("no command given; pass it after '--', e.g. run HEAD~3..HEAD -- pytest")

        def print_result(result):
            print(f"{result.sha[:12]}  {result.seconds:8.3f}s  {result.subject}")

        try:
            results = runner.run_range(
                Path.cwd(),
                args.range,
                command,
                on_result=print_result,
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

    if args.action == "bisect":
        if not command:
            parser.error(
                "no command given; pass it after '--', "
                "e.g. bisect HEAD~20..HEAD --threshold 2.0 -- pytest"
            )

        def print_result(result):
            print(f"{result.sha[:12]}  {result.seconds:8.3f}s  {result.subject}")

        try:
            culprit = runner.bisect_range(
                Path.cwd(),
                args.range,
                command,
                args.threshold,
                on_result=print_result,
            )
        except (gitutils.GitError, ValueError) as exc:
            print(f"git-bench: {exc}", file=sys.stderr)
            return 1

        if culprit is None:
            print(f"git-bench: no commit in range exceeded {args.threshold}s")
            return 1
        print(
            f"git-bench: first commit over {args.threshold}s is "
            f"{culprit.sha[:12]}  {culprit.subject}"
        )
        return 0

    if args.action == "check":
        if not command:
            parser.error(
                "no command given; pass it after '--', "
                "e.g. check main --max-regression 10 -- pytest"
            )

        def print_result(result):
            print(f"{result.sha[:12]}  {result.seconds:8.3f}s  {result.subject}")

        try:
            outcome = runner.check_regression(
                Path.cwd(),
                args.baseline,
                command,
                args.max_regression,
                on_result=print_result,
            )
        except (gitutils.GitError, ValueError) as exc:
            print(f"git-bench: {exc}", file=sys.stderr)
            return 1

        sign = "+" if outcome.regression_percent >= 0 else ""
        print(
            f"git-bench: baseline {outcome.baseline.seconds:.3f}s -> "
            f"HEAD {outcome.head.seconds:.3f}s "
            f"({sign}{outcome.regression_percent:.1f}%, limit {args.max_regression:.1f}%)"
        )

        if outcome.baseline.returncode != 0 or outcome.head.returncode != 0:
            print(
                "git-bench: command exited non-zero during check "
                f"(baseline rc={outcome.baseline.returncode}, head rc={outcome.head.returncode})",
                file=sys.stderr,
            )
            return 1

        if outcome.exceeded:
            print(
                f"git-bench: HEAD is slower than {args.baseline} by more than "
                f"{args.max_regression:.1f}%",
                file=sys.stderr,
            )
            return 1
        return 0

    if args.action == "install":
        try:
            result = install.install(Path.cwd(), global_scope=args.global_scope)
        except (gitutils.GitError, FileNotFoundError) as exc:
            print(f"git-bench: {exc}", file=sys.stderr)
            return 1
        print(
            f"git-bench: alias 'git bench' -> {result.alias_command[1:]} "
            f"({result.alias_scope})"
        )
        print(f"git-bench: cache dir ready at {result.cache_dir}")
        if result.exclude_added:
            print(f"git-bench: excluded {result.cache_dir.name}/ in {result.exclude_file}")
        else:
            print(f"git-bench: {result.cache_dir.name}/ already excluded in {result.exclude_file}")
        return 0

    if args.action == "report":
        try:
            repo = gitutils.repo_root(Path.cwd())
            results_file = storage.results_path(repo)
            _, entries = report.load_command_entries(results_file, args.report_command)
        except (gitutils.GitError, ValueError) as exc:
            print(f"git-bench: {exc}", file=sys.stderr)
            return 1
        print(report.render_report(entries))
        return 0

    parser.error(f"unknown action {args.action!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
