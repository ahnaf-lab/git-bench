"""The range runner: checks out each commit in a range into a scratch git
worktree, runs the caller's command there, times it, and logs the result.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from . import gitutils, storage


@dataclass(frozen=True)
class CommitResult:
    sha: str
    subject: str
    seconds: float
    returncode: int
    timestamp: float


def run_range(
    repo: Path,
    rev_range: str,
    command: List[str],
    results_file: Optional[Path] = None,
    on_result: Optional[Callable[[CommitResult], None]] = None,
) -> List[CommitResult]:
    """Time ``command`` at every commit in ``rev_range``, oldest first.

    For each commit a temporary ``git worktree`` is created, the command is
    run with that worktree as its working directory, and the wall-clock
    duration is recorded. Each result is appended to the local JSON store as
    soon as it is known, so a long run that is interrupted still keeps the
    commits it already timed.
    """
    if not command:
        raise ValueError("command must be a non-empty list of arguments")

    repo = gitutils.repo_root(repo)
    commits = gitutils.resolve_range(repo, rev_range)
    results_file = results_file or storage.results_path(repo)
    command_str = " ".join(command)

    results: List[CommitResult] = []
    scratch_root = Path(tempfile.mkdtemp(prefix="git-bench-"))
    try:
        for index, commit in enumerate(commits):
            worktree_path = scratch_root / f"{index:04d}-{commit.sha[:12]}"
            gitutils.add_worktree(repo, worktree_path, commit.sha)
            try:
                start = time.perf_counter()
                proc = _run_command(command, cwd=worktree_path)
                elapsed = time.perf_counter() - start
            finally:
                gitutils.remove_worktree(repo, worktree_path)

            result = CommitResult(
                sha=commit.sha,
                subject=commit.subject,
                seconds=elapsed,
                returncode=proc,
                timestamp=time.time(),
            )
            results.append(result)
            storage.append_run(
                results_file,
                command_str,
                {
                    "commit": result.sha,
                    "subject": result.subject,
                    "seconds": round(result.seconds, 6),
                    "returncode": result.returncode,
                    "timestamp": result.timestamp,
                },
            )
            if on_result is not None:
                on_result(result)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    return results


def _run_command(command: List[str], cwd: Path) -> int:
    import subprocess

    proc = subprocess.run(command, cwd=str(cwd), stdout=sys.stdout, stderr=sys.stderr)
    return proc.returncode
