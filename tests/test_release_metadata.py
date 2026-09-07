import tomllib
import unittest
from pathlib import Path

from statebraid import __version__


ROOT = Path(__file__).resolve().parents[1]


class ReleaseMetadataContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        cls.project = cls.pyproject["project"]

    def test_pep639_license_metadata_is_explicit(self) -> None:
        self.assertEqual(self.project["license"], "MIT")
        self.assertEqual(
            self.project["license-files"],
            ["LICENSE", "THIRD_PARTY_NOTICES.md"],
        )
        self.assertTrue((ROOT / "LICENSE").is_file())
        self.assertTrue((ROOT / "THIRD_PARTY_NOTICES.md").is_file())
        self.assertNotIn(
            "License ::",
            "\n".join(self.project.get("classifiers", [])),
        )

    def test_build_backend_supports_pep639_metadata(self) -> None:
        requires = self.pyproject["build-system"]["requires"]
        self.assertIn("setuptools>=77.0.3", requires)

    def test_project_metadata_is_release_candidate_complete(self) -> None:
        self.assertEqual(self.project["version"], __version__)
        self.assertEqual(self.project["readme"], "README.md")
        self.assertEqual(self.project["requires-python"], ">=3.11")
        self.assertEqual(self.project["authors"], [{"name": "StateBraid contributors"}])
        self.assertTrue(self.project["keywords"])
        urls = self.project["urls"]
        for key in ("Homepage", "Repository", "Issues", "Changelog"):
            with self.subTest(key=key):
                self.assertIn(key, urls)

    def test_python_ci_matrix_is_reflected_in_classifiers(self) -> None:
        classifiers = set(self.project["classifiers"])
        for minor in ("3.11", "3.12", "3.13", "3.14"):
            with self.subTest(minor=minor):
                self.assertIn(f"Programming Language :: Python :: {minor}", classifiers)

    def test_legal_files_keep_distinct_statebraid_and_upstream_notices(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 StateBraid contributors", license_text)
        self.assertIn("Copyright © 2023 Apple Inc.", notices)
        self.assertIn("StateBraid itself is distributed under the MIT License", notices)
        self.assertNotIn("has not yet been selected", notices)

    def test_release_docs_freeze_rc_and_tag_policy(self) -> None:
        process = (ROOT / "docs" / "RELEASE_PROCESS.md").read_text(encoding="utf-8")
        checklist = (ROOT / "docs" / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("v0.1.0rc1", process)
        self.assertIn("without creating a tag or GitHub Release", process)
        self.assertIn("do **not** create the formal v0.1", checklist)
        self.assertIn("## 0.1.0rc1 - 2026-09-07", changelog)


if __name__ == "__main__":
    unittest.main()
