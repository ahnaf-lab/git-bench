import shutil
import sys
import unittest
from pathlib import Path

from git_bench import runner, storage

from .helpers import commit_file, init_repo


class RunRangeTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_times_each_commit_and_logs_json(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        sha2 = commit_file(self.repo, "a.txt", "2", "second")
        sha3 = commit_file(self.repo, "a.txt", "3", "third")

        command = [sys.executable, "-c", "pass"]
        results = runner.run_range(self.repo, f"{sha1}..{sha3}", command)

        self.assertEqual([r.sha for r in results], [sha2, sha3])
        for result in results:
            self.assertGreaterEqual(result.seconds, 0.0)
            self.assertEqual(result.returncode, 0)

        results_file = storage.results_path(self.repo)
        self.assertTrue(results_file.exists())
        data = storage.load(results_file)
        command_str = " ".join(command)
        self.assertIn(command_str, data)
        self.assertEqual(len(data[command_str]), 2)
        self.assertEqual(data[command_str][0]["commit"], sha2)
        self.assertEqual(data[command_str][1]["commit"], sha3)

    def test_no_leftover_worktrees_after_run(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        sha2 = commit_file(self.repo, "a.txt", "2", "second")
        runner.run_range(self.repo, f"{sha1}..{sha2}", [sys.executable, "-c", "pass"])

        from git_bench import gitutils

        out = gitutils._run_git(["worktree", "list", "--porcelain"], cwd=self.repo)
        # Only the main worktree (the repo itself) should remain.
        self.assertEqual(out.count("worktree "), 1)

    def test_nonzero_exit_is_recorded_not_raised(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        sha2 = commit_file(self.repo, "a.txt", "2", "second")
        results = runner.run_range(
            self.repo, f"{sha1}..{sha2}", [sys.executable, "-c", "import sys; sys.exit(3)"]
        )
        self.assertEqual(results[0].returncode, 3)

    def test_rejects_empty_command(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        commit_file(self.repo, "a.txt", "2", "second")
        with self.assertRaises(ValueError):
            runner.run_range(self.repo, f"{sha1}..HEAD", [])


if __name__ == "__main__":
    unittest.main()
