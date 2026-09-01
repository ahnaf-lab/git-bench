import shutil
import tempfile
import unittest
from pathlib import Path

from git_bench import storage


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="git-bench-storage-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = storage.results_path(self.tmp)

    def test_load_missing_file_returns_empty_dict(self):
        self.assertEqual(storage.load(self.path), {})

    def test_append_run_persists_and_groups_by_command(self):
        storage.append_run(
            self.path,
            "pytest -q",
            {"commit": "aaa", "subject": "one", "seconds": 1.5, "returncode": 0, "timestamp": 1.0},
        )
        data = storage.append_run(
            self.path,
            "pytest -q",
            {"commit": "bbb", "subject": "two", "seconds": 1.7, "returncode": 0, "timestamp": 2.0},
        )

        self.assertEqual(list(data.keys()), ["pytest -q"])
        self.assertEqual(len(data["pytest -q"]), 2)
        self.assertEqual(data["pytest -q"][0]["commit"], "aaa")
        self.assertEqual(data["pytest -q"][1]["commit"], "bbb")

        reloaded = storage.load(self.path)
        self.assertEqual(reloaded, data)

    def test_corrupt_file_is_treated_as_empty(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("not json", encoding="utf-8")
        self.assertEqual(storage.load(self.path), {})


if __name__ == "__main__":
    unittest.main()
