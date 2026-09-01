"""Unit tests for the pure bisect-search algorithm, against synthetic timing
series (no git, no subprocess) plus integration tests wiring it to real
commits.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

from git_bench import runner

from .helpers import commit_file, init_repo


class BisectFirstOverTest(unittest.TestCase):
    def _time_at(self, series):
        calls = []

        def time_at(index: int) -> float:
            calls.append(index)
            return series[index]

        return time_at, calls

    def test_finds_step_change_in_middle(self):
        series = [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.9]
        time_at, calls = self._time_at(series)
        index = runner.bisect_first_over(len(series), 0.5, time_at)
        self.assertEqual(index, 3)
        # Binary search over 7 elements should need far fewer probes than a
        # linear scan (7); log2(7) ~= 2.8, so a handful of calls is right.
        self.assertLess(len(calls), len(series))

    def test_returns_none_when_nothing_crosses_threshold(self):
        series = [0.1, 0.2, 0.15, 0.3, 0.25]
        time_at, _ = self._time_at(series)
        index = runner.bisect_first_over(len(series), 10.0, time_at)
        self.assertIsNone(index)

    def test_first_element_already_over_threshold(self):
        series = [5.0, 5.1, 5.2]
        time_at, _ = self._time_at(series)
        index = runner.bisect_first_over(len(series), 1.0, time_at)
        self.assertEqual(index, 0)

    def test_last_element_is_the_regression(self):
        series = [0.1, 0.1, 0.1, 0.1, 9.0]
        time_at, _ = self._time_at(series)
        index = runner.bisect_first_over(len(series), 1.0, time_at)
        self.assertEqual(index, 4)

    def test_empty_series_returns_none(self):
        time_at, _ = self._time_at([])
        self.assertIsNone(runner.bisect_first_over(0, 1.0, time_at))

    def test_probe_count_is_logarithmic(self):
        # 65 elements: a linear scan would need up to 65 probes; binary
        # search should need well under 10 (ceil(log2(65)) + a couple of
        # boundary checks).
        n = 65
        series = [0.1] * 40 + [9.0] * (n - 40)
        time_at, calls = self._time_at(series)
        index = runner.bisect_first_over(n, 1.0, time_at)
        self.assertEqual(index, 40)
        self.assertLessEqual(len(calls), 10)


class BisectRangeIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_bisect_range_finds_the_slow_commit(self):
        sha0 = commit_file(self.repo, "a.txt", "0", "start")
        commit_file(self.repo, "a.txt", "1", "fast one")
        commit_file(self.repo, "a.txt", "2", "fast two")
        sha3 = commit_file(self.repo, "a.txt", "3", "the regression")
        sha4 = commit_file(self.repo, "a.txt", "4", "still slow")

        # A command whose sleep time depends on file content: fast for "0",
        # "1" and "2", slow from "3" onward, simulating a real regression.
        # ``sha0..sha4`` excludes sha0 itself, so the timed range is
        # ["1", "2", "3", "4"]. The threshold sits well clear of both the
        # 0s "fast" case and the 1.5s "slow" case (a wide 0.5s margin on
        # each side) so interpreter/process startup jitter under a loaded
        # test run can't flip a classification.
        script = (
            "import pathlib, time, sys\n"
            "content = pathlib.Path('a.txt').read_text().strip()\n"
            "time.sleep(1.5 if content in ('3', '4') else 0.0)\n"
        )
        command = [sys.executable, "-c", script]

        culprit = runner.bisect_range(self.repo, f"{sha0}..{sha4}", command, threshold=1.0)

        self.assertIsNotNone(culprit)
        self.assertEqual(culprit.sha, sha3)
        self.assertEqual(culprit.subject, "the regression")

    def test_bisect_range_returns_none_when_all_under_threshold(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        sha2 = commit_file(self.repo, "a.txt", "2", "second")

        culprit = runner.bisect_range(
            self.repo, f"{sha1}..{sha2}", [sys.executable, "-c", "pass"], threshold=10.0
        )
        self.assertIsNone(culprit)

    def test_bisect_range_rejects_empty_command(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        commit_file(self.repo, "a.txt", "2", "second")
        with self.assertRaises(ValueError):
            runner.bisect_range(self.repo, f"{sha1}..HEAD", [], threshold=1.0)

    def test_bisect_range_rejects_non_positive_threshold(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        commit_file(self.repo, "a.txt", "2", "second")
        with self.assertRaises(ValueError):
            runner.bisect_range(
                self.repo, f"{sha1}..HEAD", [sys.executable, "-c", "pass"], threshold=0.0
            )


if __name__ == "__main__":
    unittest.main()
