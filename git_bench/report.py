"""Render an ASCII sparkline and table for previously recorded bench runs.

Reads whatever ``git bench run`` already wrote to the local JSON store (see
``storage.py``) and renders it for a human — no new data is collected here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import storage

# Purely ASCII ramp from "shortest" to "longest", used to bucket each
# timing into one of ``len(SPARK_LEVELS)`` relative levels.
SPARK_LEVELS = " .-:=+*#%@"


def sparkline(values: List[float]) -> str:
    """Render ``values`` as a single-line ASCII sparkline.

    Each value is bucketed into one of ``len(SPARK_LEVELS)`` levels between
    the series' min and max, so the shape shows relative change even when
    absolute seconds are tiny. A flat series (min == max) renders as a solid
    line of the middle character rather than dividing by zero.
    """
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        mid = SPARK_LEVELS[len(SPARK_LEVELS) // 2]
        return mid * len(values)
    span = hi - lo
    top = len(SPARK_LEVELS) - 1
    chars = []
    for value in values:
        level = round((value - lo) / span * top)
        chars.append(SPARK_LEVELS[level])
    return "".join(chars)


def format_table(entries: List[Dict[str, Any]]) -> str:
    """Render ``entries`` (as stored by ``storage.append_run``) as a table."""
    header = f"{'commit':12}  {'seconds':>10}  {'rc':>3}  subject"
    lines = [header, "-" * len(header)]
    for entry in entries:
        sha = str(entry.get("commit", ""))[:12]
        seconds = float(entry.get("seconds", 0.0))
        returncode = entry.get("returncode", "")
        subject = str(entry.get("subject", ""))
        lines.append(f"{sha:12}  {seconds:10.3f}  {returncode!s:>3}  {subject}")
    return "\n".join(lines)


def render_report(entries: List[Dict[str, Any]]) -> str:
    """Render the full sparkline + table report for one command's entries."""
    if not entries:
        return "no recorded runs"
    values = [float(entry.get("seconds", 0.0)) for entry in entries]
    return "\n".join([sparkline(values), "", format_table(entries)])


def load_command_entries(
    results_file: Path, command: Optional[str] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """Return ``(command, entries)`` for the command to report on.

    If ``command`` is given it is looked up directly (an unknown command
    yields an empty list, not an error, so a typo reports "no recorded runs"
    rather than crashing). Otherwise, if the store holds results for exactly
    one command that command is used; with zero or more than one recorded
    command, a ``ValueError`` explains what to pass instead.
    """
    data = storage.load(results_file)
    if command is not None:
        return command, data.get(command, [])
    if not data:
        raise ValueError(
            "no recorded runs; run 'git bench run <range> -- <command>' first"
        )
    if len(data) == 1:
        ((only_command, entries),) = data.items()
        return only_command, entries
    available = ", ".join(sorted(data))
    raise ValueError(
        f"multiple commands recorded ({available}); pass one with --command"
    )
