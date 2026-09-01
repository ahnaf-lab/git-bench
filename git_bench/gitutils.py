"""Thin wrappers around the ``git`` CLI, used to walk a commit range and
manage the throwaway worktrees each commit is timed in.

Every git invocation passes arguments as a list (never through a shell), so
values such as revision ranges or commit hashes cannot be interpreted as
shell syntax.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List


class GitError(RuntimeError):
    """Raised when a git command fails."""


def _run_git(args: List[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout


def repo_root(start: Path) -> Path:
    """Return the top-level directory of the git repo containing ``start``."""
    out = _run_git(["rev-parse", "--show-toplevel"], cwd=start)
    return Path(out.strip())


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str


def resolve_range(repo: Path, rev_range: str) -> List[Commit]:
    """Resolve a revision range (e.g. ``abc123..def456`` or ``HEAD~3..HEAD``)
    into a list of commits, oldest first.
    """
    out = _run_git(
        ["rev-list", "--reverse", "--pretty=format:%H\t%s", rev_range],
        cwd=repo,
    )
    commits = []
    for line in out.splitlines():
        if line.startswith("commit "):
            continue
        if "\t" not in line:
            continue
        sha, subject = line.split("\t", 1)
        commits.append(Commit(sha=sha, subject=subject))
    if not commits:
        raise GitError(f"revision range {rev_range!r} contains no commits")
    return commits


def add_worktree(repo: Path, worktree_path: Path, commit_sha: str) -> None:
    _run_git(
        ["worktree", "add", "--detach", "--quiet", str(worktree_path), commit_sha],
        cwd=repo,
    )


def remove_worktree(repo: Path, worktree_path: Path) -> None:
    _run_git(
        ["worktree", "remove", "--force", str(worktree_path)],
        cwd=repo,
    )
