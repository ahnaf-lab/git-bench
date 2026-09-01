"""The range runner: checks out each commit in a range into a scratch git
worktree, runs the caller's command there, times it, and logs the result.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

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
            result = _time_commit(repo, scratch_root, index, commit, command)
            results.append(result)
            _record(results_file, command_str, result, on_result)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    return results


def bisect_range(
    repo: Path,
    rev_range: str,
    command: List[str],
    threshold: float,
    results_file: Optional[Path] = None,
    on_result: Optional[Callable[[CommitResult], None]] = None,
) -> Optional[CommitResult]:
    """Binary-search ``rev_range`` for the first commit (oldest to newest)
    whose ``command`` takes longer than ``threshold`` seconds.

    This assumes timings are monotonic across the range: once a commit's
    timing crosses the threshold, every later commit in the range does too.
    Under that assumption, only O(log n) commits need to be timed instead of
    every commit in the range (what ``run_range`` does). Each commit that
    *is* timed is still recorded to ``results_file``, same as ``run_range``.

    Returns the ``CommitResult`` for the first commit over threshold, or
    ``None`` if no commit in the range exceeds it.
    """
    if not command:
        raise ValueError("command must be a non-empty list of arguments")
    if threshold <= 0:
        raise ValueError("threshold must be a positive number of seconds")

    repo = gitutils.repo_root(repo)
    commits = gitutils.resolve_range(repo, rev_range)
    results_file = results_file or storage.results_path(repo)
    command_str = " ".join(command)

    scratch_root = Path(tempfile.mkdtemp(prefix="git-bench-bisect-"))
    cache: Dict[int, CommitResult] = {}

    def time_at(index: int) -> float:
        if index not in cache:
            result = _time_commit(repo, scratch_root, index, commits[index], command)
            cache[index] = result
            _record(results_file, command_str, result, on_result)
        return cache[index].seconds

    try:
        found_index = bisect_first_over(len(commits), threshold, time_at)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    return cache[found_index] if found_index is not None else None


@dataclass(frozen=True)
class CheckResult:
    baseline: CommitResult
    head: CommitResult
    regression_percent: float
    exceeded: bool


def regression_percent(baseline_seconds: float, head_seconds: float) -> float:
    """Return how much slower (or faster, as a negative number) ``head_seconds``
    is than ``baseline_seconds``, as a percentage of the baseline.
    """
    if baseline_seconds <= 0:
        raise ValueError("baseline seconds must be a positive number")
    return (head_seconds - baseline_seconds) / baseline_seconds * 100.0


def check_regression(
    repo: Path,
    baseline_rev: str,
    command: List[str],
    max_regression_percent: float,
    results_file: Optional[Path] = None,
    on_result: Optional[Callable[[CommitResult], None]] = None,
) -> CheckResult:
    """Time ``command`` at ``baseline_rev`` and at ``HEAD`` and compare them.

    Both commits are timed the same way ``run_range`` times each commit (a
    throwaway ``git worktree``, so the current working tree and index are
    never touched) and each timing is still appended to the local JSON
    store. ``exceeded`` is ``True`` when HEAD is slower than the baseline by
    more than ``max_regression_percent`` percent.
    """
    if not command:
        raise ValueError("command must be a non-empty list of arguments")
    if max_regression_percent < 0:
        raise ValueError("max_regression_percent must not be negative")

    repo = gitutils.repo_root(repo)
    baseline_commit = gitutils.resolve_commit(repo, baseline_rev)
    head_commit = gitutils.resolve_commit(repo, "HEAD")
    results_file = results_file or storage.results_path(repo)
    command_str = " ".join(command)

    scratch_root = Path(tempfile.mkdtemp(prefix="git-bench-check-"))
    try:
        baseline_result = _time_commit(repo, scratch_root, 0, baseline_commit, command)
        _record(results_file, command_str, baseline_result, on_result)
        head_result = _time_commit(repo, scratch_root, 1, head_commit, command)
        _record(results_file, command_str, head_result, on_result)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    pct = regression_percent(baseline_result.seconds, head_result.seconds)
    exceeded = pct > max_regression_percent
    return CheckResult(
        baseline=baseline_result,
        head=head_result,
        regression_percent=pct,
        exceeded=exceeded,
    )


def bisect_first_over(
    length: int, threshold: float, time_at: Callable[[int], float]
) -> Optional[int]:
    """Binary-search the index range ``[0, length)`` for the first index
    whose value (from calling ``time_at(index)``) exceeds ``threshold``.

    ``time_at`` is assumed non-decreasing once it first crosses the
    threshold (a monotonic regression: nothing gets fast again). Pure
    index/threshold logic, kept separate from git and process plumbing so it
    can be unit-tested against a synthetic timing series.

    Returns ``None`` if ``length`` is 0 or no index exceeds the threshold.
    """
    if length == 0:
        return None
    if time_at(length - 1) <= threshold:
        return None
    if time_at(0) > threshold:
        return 0

    lo, hi = 0, length - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if time_at(mid) > threshold:
            hi = mid
        else:
            lo = mid
    return hi


def _time_commit(repo: Path, scratch_root: Path, index: int, commit, command: List[str]) -> CommitResult:
    worktree_path = scratch_root / f"{index:04d}-{commit.sha[:12]}"
    gitutils.add_worktree(repo, worktree_path, commit.sha)
    try:
        start = time.perf_counter()
        proc = _run_command(command, cwd=worktree_path)
        elapsed = time.perf_counter() - start
    finally:
        gitutils.remove_worktree(repo, worktree_path)

    return CommitResult(
        sha=commit.sha,
        subject=commit.subject,
        seconds=elapsed,
        returncode=proc,
        timestamp=time.time(),
    )


def _record(
    results_file: Path,
    command_str: str,
    result: CommitResult,
    on_result: Optional[Callable[[CommitResult], None]],
) -> None:
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


def _run_command(command: List[str], cwd: Path) -> int:
    import subprocess

    # No stdout/stderr= given: the child inherits the real process file
    # descriptors directly, rather than going through ``sys.stdout``/
    # ``sys.stderr`` (which may be swapped for something without a file
    # descriptor, e.g. in tests, and would break the subprocess).
    proc = subprocess.run(command, cwd=str(cwd))
    return proc.returncode
