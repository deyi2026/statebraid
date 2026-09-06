import unittest

from statebraid import __version__


class IdentityTest(unittest.TestCase):
    def test_version_marks_v01_development_boundary(self):
        self.assertTrue(__version__.startswith("0.1."))


if __name__ == "__main__":
    unittest.main()
