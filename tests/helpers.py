"""Shared helpers for building a throwaway git repo to test against."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import List


def run(args: List[str], cwd: Path) -> None:
    subprocess.run(args, cwd=str(cwd), check=True, capture_output=True, text=True)


def init_repo() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="git-bench-test-"))
    run(["git", "init", "--quiet"], cwd=tmp)
    run(["git", "config", "user.email", "test@example.com"], cwd=tmp)
    run(["git", "config", "user.name", "Test"], cwd=tmp)
    return tmp


def commit_file(repo: Path, name: str, content: str, message: str) -> str:
    (repo / name).write_text(content, encoding="utf-8")
    run(["git", "add", name], cwd=repo)
    run(["git", "commit", "--quiet", "-m", message], cwd=repo)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    )
    return out.stdout.strip()
