"""Tests for the sparkline/table report, exercised against fixture logs."""

from __future__ import annotations

import unittest
from pathlib import Path

from git_bench import report

FIXTURES = Path(__file__).parent / "fixtures"


class SparklineTest(unittest.TestCase):
    def test_increasing_values_produce_increasing_levels(self):
        line = report.sparkline([1.0, 2.5, 5.0])
        levels = [report.SPARK_LEVELS.index(ch) for ch in line]
        self.assertEqual(levels, sorted(levels))
        self.assertEqual(levels[0], 0)
        self.assertEqual(levels[-1], len(report.SPARK_LEVELS) - 1)

    def test_flat_series_has_no_divide_by_zero(self):
        line = report.sparkline([2.0, 2.0, 2.0])
        self.assertEqual(len(line), 3)
        self.assertEqual(len(set(line)), 1)

    def test_empty_series_is_empty_string(self):
        self.assertEqual(report.sparkline([]), "")


class LoadFixtureTest(unittest.TestCase):
    def test_single_command_fixture_is_auto_selected(self):
        path = FIXTURES / "results_single_command.json"
        command, entries = report.load_command_entries(path)
        self.assertEqual(command, "pytest -q")
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["commit"][:12], "aaaaaaaaaaaa")

    def test_multi_command_fixture_requires_explicit_command(self):
        path = FIXTURES / "results_multi_command.json"
        with self.assertRaises(ValueError):
            report.load_command_entries(path)

        command, entries = report.load_command_entries(path, command="make test")
        self.assertEqual(command, "make test")
        self.assertEqual(len(entries), 1)

    def test_missing_store_raises_value_error(self):
        with self.assertRaises(ValueError):
            report.load_command_entries(FIXTURES / "does-not-exist.json")


class RenderReportTest(unittest.TestCase):
    def test_render_report_includes_sparkline_and_table_rows(self):
        _, entries = report.load_command_entries(
            FIXTURES / "results_single_command.json"
        )
        text = report.render_report(entries)
        lines = text.splitlines()

        # First line is the sparkline: one ASCII char per recorded commit.
        self.assertEqual(len(lines[0]), len(entries))

        self.assertIn("commit", lines[2])
        self.assertIn("seconds", lines[2])
        self.assertIn("aaaaaaaaaaaa", text)
        self.assertIn("third commit, much slower", text)
        self.assertIn("5.000", text)

    def test_render_report_empty_entries(self):
        self.assertEqual(report.render_report([]), "no recorded runs")


if __name__ == "__main__":
    unittest.main()
