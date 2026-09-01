import io
import os
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from git_bench import cli, storage

from .helpers import commit_file, init_repo


class CliRunTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self._cwd = Path.cwd()
        self.addCleanup(lambda: None)

    def test_run_action_executes_and_returns_zero(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        sha2 = commit_file(self.repo, "a.txt", "2", "second")

        old_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            rc = cli.main(["run", f"{sha1}..{sha2}", "--", sys.executable, "-c", "pass"])
        finally:
            os.chdir(old_cwd)

        self.assertEqual(rc, 0)
        data = storage.load(storage.results_path(self.repo))
        command_str = f"{sys.executable} -c pass"
        self.assertIn(command_str, data)
        self.assertEqual(len(data[command_str]), 1)

    def test_missing_command_is_a_usage_error(self):
        with self.assertRaises(SystemExit):
            cli.main(["run", "HEAD~1..HEAD"])


class CliBisectTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def _run_in_repo(self, argv, capture=False):
        old_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            if not capture:
                return cli.main(argv), ""
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli.main(argv)
            return rc, out.getvalue()
        finally:
            os.chdir(old_cwd)

    def test_bisect_reports_the_first_slow_commit(self):
        sha0 = commit_file(self.repo, "a.txt", "0", "start")
        commit_file(self.repo, "a.txt", "1", "fast")
        commit_file(self.repo, "a.txt", "2", "fast still")
        sha3 = commit_file(self.repo, "a.txt", "3", "regression")

        script = (
            "import pathlib, time\n"
            "content = pathlib.Path('a.txt').read_text().strip()\n"
            "time.sleep(0.6 if content == '3' else 0.0)\n"
        )
        rc, output = self._run_in_repo(
            [
                "bisect",
                f"{sha0}..{sha3}",
                "--threshold",
                "0.3",
                "--",
                sys.executable,
                "-c",
                script,
            ],
            capture=True,
        )
        self.assertEqual(rc, 0)
        self.assertIn(sha3[:12], output)

    def test_bisect_missing_command_is_a_usage_error(self):
        with self.assertRaises(SystemExit):
            cli.main(["bisect", "HEAD~1..HEAD", "--threshold", "1.0"])

    def test_bisect_no_commit_over_threshold_exits_nonzero(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        sha2 = commit_file(self.repo, "a.txt", "2", "second")
        rc, output = self._run_in_repo(
            ["bisect", f"{sha1}..{sha2}", "--threshold", "10.0", "--", sys.executable, "-c", "pass"],
            capture=True,
        )
        self.assertEqual(rc, 1)
        self.assertIn("no commit", output)


class CliReportTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def _run_in_repo(self, argv, capture=False):
        old_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            if not capture:
                return cli.main(argv), ""
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli.main(argv)
            return rc, out.getvalue()
        finally:
            os.chdir(old_cwd)

    def test_report_after_run_shows_sparkline_and_table(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        sha2 = commit_file(self.repo, "a.txt", "2", "second")
        # subprocess.run needs a real stdout fd, so don't capture this call.
        rc, _ = self._run_in_repo(
            ["run", f"{sha1}..{sha2}", "--", sys.executable, "-c", "pass"]
        )
        self.assertEqual(rc, 0)

        rc, output = self._run_in_repo(["report"], capture=True)
        self.assertEqual(rc, 0)
        self.assertIn("commit", output)
        self.assertIn("seconds", output)
        self.assertIn(sha2[:12], output)

    def test_report_with_no_recorded_runs_is_an_error(self):
        commit_file(self.repo, "a.txt", "1", "first")
        rc, _ = self._run_in_repo(["report"], capture=True)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
