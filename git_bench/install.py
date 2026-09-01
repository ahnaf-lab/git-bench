"""``git bench install``: wire the ``git bench`` alias and prepare the local
results cache directory.

Safe to run from a linked worktree (``git worktree add``): the alias is
written to git config at the requested scope, and the results-cache exclude
rule is appended to ``info/exclude`` inside the *common* git directory (see
``gitutils.git_common_dir``), which every worktree shares. Nothing is ever
written to a tracked file such as ``.gitignore``, so the cache directory
never shows up as an uncommitted change and every worktree — including ones
that never check out the file that would otherwise hold the ignore rule —
sees it as ignored.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from . import gitutils, storage

ALIAS_NAME = "bench"


@dataclass(frozen=True)
class InstallResult:
    alias_command: str
    alias_scope: str
    cache_dir: Path
    exclude_file: Path
    exclude_added: bool


def find_git_bench() -> str:
    """Return the command the git alias should invoke.

    Prefers an already-installed ``git-bench`` console script (e.g. from
    ``pip install -e .``) found on ``PATH``. Falls back to this repo's
    ``bin/git-bench`` shim, run through the current Python interpreter by
    absolute path, so ``install`` still works before the package has been
    pip-installed anywhere.
    """
    on_path = shutil.which("git-bench")
    if on_path:
        return on_path
    shim = Path(__file__).resolve().parent.parent / "bin" / "git-bench"
    if shim.exists():
        return f"{sys.executable} {shim}"
    raise FileNotFoundError(
        "could not find a 'git-bench' executable on PATH or bin/git-bench "
        "next to the git_bench package"
    )


def install(repo: Path, global_scope: bool = False) -> InstallResult:
    """Wire the ``git bench`` alias and prepare ``.git-bench/`` for ``repo``.

    Idempotent: running this more than once updates the alias in place and
    never duplicates the exclude entry.
    """
    repo_root = gitutils.repo_root(repo)
    target = find_git_bench()
    alias_command = f"!{target}"
    gitutils.set_config(
        repo_root, f"alias.{ALIAS_NAME}", alias_command, global_scope=global_scope
    )

    cache_dir = repo_root / storage.DEFAULT_RESULTS_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    common_dir = gitutils.git_common_dir(repo_root)
    exclude_file = common_dir / "info" / "exclude"
    exclude_added = _ensure_excluded(exclude_file, f"{storage.DEFAULT_RESULTS_DIR}/")

    return InstallResult(
        alias_command=alias_command,
        alias_scope="global" if global_scope else "local",
        cache_dir=cache_dir,
        exclude_file=exclude_file,
        exclude_added=exclude_added,
    )


def _ensure_excluded(exclude_file: Path, pattern: str) -> bool:
    """Append ``pattern`` to ``exclude_file`` unless it is already there.

    Returns ``True`` if the pattern was added, ``False`` if it was already
    present.
    """
    exclude_file.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if exclude_file.exists():
        existing = exclude_file.read_text(encoding="utf-8")
    if pattern in existing.splitlines():
        return False
    with exclude_file.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(f"{pattern}\n")
    return True
