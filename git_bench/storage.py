"""Local JSON storage for bench results.

Results are grouped by the exact command string that produced them, since
timings for different commands are not comparable. Each entry records the
commit, its subject line, wall-clock seconds, the process return code, and
when the run happened.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_RESULTS_DIR = ".git-bench"
DEFAULT_RESULTS_FILE = "results.json"


def results_path(repo_root: Path) -> Path:
    return repo_root / DEFAULT_RESULTS_DIR / DEFAULT_RESULTS_FILE


def load(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError:
            return {}
    if not isinstance(data, dict):
        return {}
    return data


def save(path: Path, data: Dict[str, List[Dict[str, Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp_path.replace(path)


def append_run(
    path: Path,
    command: str,
    entry: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """Append a single commit's result under ``command`` and persist it.

    Returns the full data structure after the append.
    """
    data = load(path)
    runs = data.setdefault(command, [])
    runs.append(entry)
    save(path, data)
    return data
