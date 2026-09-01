import shutil
import unittest
from pathlib import Path

from git_bench import gitutils

from .helpers import commit_file, init_repo


class ResolveRangeTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_resolves_commits_oldest_first(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        sha2 = commit_file(self.repo, "a.txt", "2", "second")
        sha3 = commit_file(self.repo, "a.txt", "3", "third")

        commits = gitutils.resolve_range(self.repo, f"{sha1}..{sha3}")

        self.assertEqual([c.sha for c in commits], [sha2, sha3])
        self.assertEqual(commits[0].subject, "second")

    def test_empty_range_raises(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        with self.assertRaises(gitutils.GitError):
            gitutils.resolve_range(self.repo, f"{sha1}..{sha1}")

    def test_worktree_add_and_remove(self):
        sha1 = commit_file(self.repo, "a.txt", "1", "first")
        worktree = self.repo.parent / "wt"
        gitutils.add_worktree(self.repo, worktree, sha1)
        self.assertTrue((worktree / "a.txt").exists())
        gitutils.remove_worktree(self.repo, worktree)
        self.assertFalse(worktree.exists())


if __name__ == "__main__":
    unittest.main()
