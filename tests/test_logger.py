import os
import logging
from src.logger import setup_logger, get_logger


class TestLoggerSetup:
    def test_creates_log_directory(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_creates_log_file(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        logger = get_logger("test")
        logger.info("test message")
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1

    def test_log_entry_format(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        logger = get_logger("ws_client")
        logger.error(
            "timer index 5 out of range",
            extra={
                "context": "processing inbound command",
                "state": "ws=connected, timers=[idle]",
            },
        )
        log_file = list(log_dir.glob("*.log"))[0]
        content = log_file.read_text()
        assert "ERROR" in content
        assert "ws_client" in content
        assert "timer index 5 out of range" in content
        assert "processing inbound command" in content
        assert "ws=connected" in content

    def test_default_extra_fields(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        logger = get_logger("timer")
        logger.info("timer started")
        log_file = list(log_dir.glob("*.log"))[0]
        content = log_file.read_text()
        assert "timer" in content
        assert "timer started" in content


class TestLoggerRetrieval:
    def test_get_logger_returns_child(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        logger = get_logger("file_writer")
        assert logger.name == "klute_timer.file_writer"
