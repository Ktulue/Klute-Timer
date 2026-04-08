import os
import winsound
from typing import Optional

from src.logger import get_logger

log = get_logger("sound_player")


class SoundPlayer:
    """Plays WAV files via winsound. Never raises.

    Failure modes (None path, missing file, invalid WAV, OS error) are
    logged and swallowed so the timer's run thread cannot be killed by
    a sound playback issue.
    """

    def play(self, path: Optional[str]) -> None:
        if path is None or not path.strip():
            return

        normalized = os.path.abspath(path)

        if not os.path.exists(normalized):
            log.warning(
                f"sound file not found: {normalized}",
                extra={"context": "play", "state": f"path={path}"},
            )
            return

        try:
            winsound.PlaySound(
                normalized,
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )
        except Exception as e:
            log.error(
                f"winsound playback failed: {e}",
                extra={"context": "play", "state": f"path={normalized}"},
            )
