import shutil
import sys
import unittest
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
        import os

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


if __name__ == "__main__":
    unittest.main()
