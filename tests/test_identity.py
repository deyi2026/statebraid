import unittest
import tomllib
from pathlib import Path

from statebraid import __version__


ROOT = Path(__file__).resolve().parents[1]


class IdentityTest(unittest.TestCase):
    def test_version_marks_v01_release_candidate_boundary(self):
        self.assertEqual(__version__, "0.1.0rc1")

    def test_distribution_version_matches_runtime_identity(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(project["version"], __version__)


if __name__ == "__main__":
    unittest.main()
