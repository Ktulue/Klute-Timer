import re

from src import version


def test_version_is_dotted_major_minor_patch():
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)


def test_version_tuple_is_the_dotted_parts_plus_zero(monkeypatch):
    monkeypatch.setattr(version, "__version__", "2.13.7")
    assert version.version_tuple() == (2, 13, 7, 0)


def test_version_tuple_matches_current_version():
    parts = tuple(int(p) for p in version.__version__.split("."))
    assert version.version_tuple() == parts + (0,)
