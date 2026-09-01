"""Unit tests for the pure regression-percent helper, plus integration tests
wiring ``check_regression`` to real commits.
"""

from __future__ import annotations

import shutil
import sys
import unittest

from git_bench import runner

from .helpers import commit_file, init_repo


class RegressionPercentTest(unittest.TestCase):
    def test_slower_head_is_a_positive_percent(self):
        pct = runner.regression_percent(baseline_seconds=1.0, head_seconds=1.5)
        self.assertAlmostEqual(pct, 50.0)

    def test_faster_head_is_a_negative_percent(self):
        pct = runner.regression_percent(baseline_seconds=2.0, head_seconds=1.0)
        self.assertAlmostEqual(pct, -50.0)

    def test_equal_timings_are_zero_percent(self):
        pct = runner.regression_percent(baseline_seconds=1.0, head_seconds=1.0)
        self.assertAlmostEqual(pct, 0.0)

    def test_rejects_non_positive_baseline(self):
        with self.assertRaises(ValueError):
            runner.regression_percent(baseline_seconds=0.0, head_seconds=1.0)


class CheckRegressionIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_flags_a_real_slowdown(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "baseline")
        commit_file(self.repo, "a.txt", "2", "the regression")

        script = (
            "import pathlib, time\n"
            "content = pathlib.Path('a.txt').read_text().strip()\n"
            "time.sleep(0.5 if content == '2' else 0.0)\n"
        )
        outcome = runner.check_regression(
            self.repo, sha1, [sys.executable, "-c", script], max_regression_percent=10.0
        )

        self.assertTrue(outcome.exceeded)
        self.assertGreater(outcome.regression_percent, 10.0)
        self.assertEqual(outcome.baseline.sha, sha1)

    def test_passes_when_head_is_not_meaningfully_slower(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "baseline")
        commit_file(self.repo, "a.txt", "2", "no real change")

        outcome = runner.check_regression(
            self.repo,
            sha1,
            [sys.executable, "-c", "pass"],
            max_regression_percent=1000.0,
        )

        self.assertFalse(outcome.exceeded)

    def test_rejects_empty_command(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "baseline")
        commit_file(self.repo, "a.txt", "2", "second")
        with self.assertRaises(ValueError):
            runner.check_regression(self.repo, sha1, [], max_regression_percent=10.0)

    def test_rejects_negative_threshold(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "baseline")
        commit_file(self.repo, "a.txt", "2", "second")
        with self.assertRaises(ValueError):
            runner.check_regression(
                self.repo, sha1, [sys.executable, "-c", "pass"], max_regression_percent=-1.0
            )


if __name__ == "__main__":
    unittest.main()
