import shutil
import unittest
from pathlib import Path

from git_bench import cli, gitutils, install, storage

from .helpers import commit_file, init_repo


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        commit_file(self.repo, "a.txt", "1", "first")

    def test_install_writes_local_alias(self):
        result = install.install(self.repo)

        self.assertEqual(result.alias_scope, "local")
        alias = gitutils.get_config(self.repo, "alias.bench")
        self.assertEqual(alias, result.alias_command)
        self.assertTrue(result.alias_command.startswith("!"))

    def test_install_creates_cache_dir_and_excludes_it(self):
        result = install.install(self.repo)

        self.assertTrue(result.cache_dir.is_dir())
        self.assertEqual(
            result.cache_dir.resolve(),
            (self.repo / storage.DEFAULT_RESULTS_DIR).resolve(),
        )
        self.assertTrue(result.exclude_file.exists())
        exclude_contents = result.exclude_file.read_text(encoding="utf-8")
        self.assertIn(f"{storage.DEFAULT_RESULTS_DIR}/", exclude_contents)

    def test_install_is_idempotent(self):
        first = install.install(self.repo)
        self.assertTrue(first.exclude_added)

        second = install.install(self.repo)
        self.assertFalse(second.exclude_added)

        exclude_contents = second.exclude_file.read_text(encoding="utf-8")
        self.assertEqual(
            exclude_contents.count(f"{storage.DEFAULT_RESULTS_DIR}/"), 1
        )

    def test_installed_cache_dir_is_not_reported_untracked(self):
        install.install(self.repo)

        status = gitutils._run_git(["status", "--porcelain"], cwd=self.repo)
        self.assertNotIn(storage.DEFAULT_RESULTS_DIR, status)

    def test_install_from_linked_worktree_shares_exclude_with_main_repo(self):
        worktree = self.repo.parent / "wt"
        head_sha = gitutils._run_git(["rev-parse", "HEAD"], cwd=self.repo).strip()
        gitutils.add_worktree(self.repo, worktree, head_sha)
        self.addCleanup(shutil.rmtree, worktree, ignore_errors=True)

        result = install.install(worktree)

        # The exclude rule lives in the *main* repo's common git dir, so it
        # also applies back in the original working tree.
        self.assertIn(str(self.repo), str(result.exclude_file))
        status = gitutils._run_git(["status", "--porcelain"], cwd=self.repo)
        self.assertNotIn(storage.DEFAULT_RESULTS_DIR, status)


class CliInstallTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        commit_file(self.repo, "a.txt", "1", "first")

    def test_cli_install_action_returns_zero(self):
        import os

        old_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            rc = cli.main(["install"])
        finally:
            os.chdir(old_cwd)

        self.assertEqual(rc, 0)
        self.assertIsNotNone(gitutils.get_config(self.repo, "alias.bench"))


if __name__ == "__main__":
    unittest.main()
