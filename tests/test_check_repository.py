from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_repository import run_checks


class RepositoryChecksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "scripts").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "README.md").write_text("# Test\n", encoding="utf-8")
        (self.root / "scripts" / "run_profile_cache_matrix.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        (self.root / "docs" / "research-map.md").write_text("# Map\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_accepts_valid_sources(self) -> None:
        (self.root / "sample.py").write_text("value = 1\n", encoding="utf-8")
        (self.root / "sample.sh").write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
        (self.root / "sample.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

        result = run_checks(self.root)

        self.assertTrue(result.ok)
        self.assertEqual((result.python_files, result.shell_files, result.json_files), (2, 1, 1))

    def test_reports_invalid_sources(self) -> None:
        (self.root / "broken.py").write_text("if True print('no')\n", encoding="utf-8")
        (self.root / "broken.sh").write_text("if true; then\n", encoding="utf-8")
        (self.root / "broken.json").write_text("{", encoding="utf-8")

        result = run_checks(self.root)

        self.assertFalse(result.ok)
        self.assertEqual(len(result.errors), 3)
        self.assertTrue(any(error.startswith("python:") for error in result.errors))
        self.assertTrue(any(error.startswith("shell:") for error in result.errors))
        self.assertTrue(any(error.startswith("json:") for error in result.errors))

    def test_ignores_generated_result_directories(self) -> None:
        generated = self.root / "prototypes" / "demo" / "results" / "run"
        generated.mkdir(parents=True)
        (generated / "broken.json").write_text("{", encoding="utf-8")

        result = run_checks(self.root)

        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
