import os
import tempfile
from typing import Optional

from src.logger import get_logger

log = get_logger("file_writer")


class FileWriter:
    def __init__(self):
        self._paths: dict[int, str] = {}

    def register(self, timer_id: int, file_path: str) -> None:
        normalized = os.path.normpath(os.path.abspath(file_path))

        for tid, existing in self._paths.items():
            if existing == normalized and tid != timer_id:
                raise ValueError(
                    f"Path '{file_path}' already assigned to timer {tid}"
                )

        old_path = self._paths.get(timer_id)
        self._paths[timer_id] = normalized

        os.makedirs(os.path.dirname(normalized), exist_ok=True)

        if old_path and old_path != normalized:
            log.info(
                f"timer {timer_id} output changed: {old_path} -> {normalized}",
                extra={"context": "register", "state": f"paths={list(self._paths.values())}"},
            )

    def unregister(self, timer_id: int) -> None:
        self._paths.pop(timer_id, None)

    def write_time(self, timer_id: int, formatted: str) -> None:
        self._atomic_write(timer_id, formatted)

    def write_end_message(self, timer_id: int, message: str) -> None:
        self._atomic_write(timer_id, message)

    def clear(self, timer_id: int) -> None:
        self._atomic_write(timer_id, "")

    def _atomic_write(self, timer_id: int, content: str) -> None:
        path = self._paths.get(timer_id)
        if path is None:
            log.warning(
                f"write attempted for unregistered timer {timer_id}",
                extra={"context": "atomic_write", "state": "no path"},
            )
            return

        dir_path = os.path.dirname(path)
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".klute_")
            try:
                os.write(fd, content.encode("utf-8"))
            finally:
                os.close(fd)
            os.replace(tmp_path, path)
        except OSError:
            log.error(
                f"failed to write to {path}",
                extra={
                    "context": f"writing timer {timer_id}",
                    "state": f"content_length={len(content)}",
                },
            )
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
