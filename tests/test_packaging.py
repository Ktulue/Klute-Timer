"""Static checks that the build files stay in step with the Python they depend on.

They catch drift (a hardcoded version, a renamed mutex) cheaply. They do not
replace building and installing: the installed exe is the arbiter.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts: str) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class TestSpec:
    def test_reads_version_from_src_version(self):
        spec = _read("KluteTimer.spec")
        assert "from src.version import __version__, version_tuple" in spec

    def test_passes_version_resource_to_exe(self):
        spec = _read("KluteTimer.spec")
        assert re.search(r"version\s*=\s*version_info", spec)

    def test_has_no_version_literal(self):
        spec = _read("KluteTimer.spec")
        assert not re.search(r"['\"]\d+\.\d+\.\d+['\"]", spec)
