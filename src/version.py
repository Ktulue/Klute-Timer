"""The one place Klute Timer's version is written.

KluteTimer.spec reads it for the exe's version resource, build.bat passes it to
the Inno Setup compiler for the installer and the Installed apps entry, and the
app shows it in Settings and the log. Bump it here and nowhere else.
"""

__version__ = "1.0.0"


def version_tuple() -> tuple[int, int, int, int]:
    """The four-part (major, minor, patch, 0) form Windows version resources use."""
    major, minor, patch = (int(part) for part in __version__.split("."))
    return (major, minor, patch, 0)
