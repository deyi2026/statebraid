from statebraid import __version__


def test_version_marks_v01_development_boundary():
    assert __version__.startswith("0.1.")
