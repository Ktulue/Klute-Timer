import os
import winsound
from unittest.mock import patch
from src.sound_player import SoundPlayer


class TestSoundPlayerSilentCases:
    def test_play_with_none_path_is_silent(self):
        player = SoundPlayer()
        player.play(None)  # must not raise

    def test_play_with_empty_string_is_silent(self):
        player = SoundPlayer()
        player.play("")  # must not raise

    def test_play_with_whitespace_string_is_silent(self):
        player = SoundPlayer()
        player.play("   ")  # must not raise


class TestSoundPlayerErrorHandling:
    def test_play_with_missing_file_does_not_raise(self, caplog):
        player = SoundPlayer()
        player.play("/nonexistent/path/to/file.wav")  # must not raise
        assert any("not found" in r.message.lower() or "does not exist" in r.message.lower()
                   for r in caplog.records)

    def test_play_with_winsound_exception_does_not_raise(self, tmp_path, caplog):
        # Create a real file so the existence check passes
        wav_path = tmp_path / "fake.wav"
        wav_path.write_bytes(b"not a real wav")

        with patch("src.sound_player.winsound.PlaySound") as mock_play:
            mock_play.side_effect = RuntimeError("simulated audio failure")
            player = SoundPlayer()
            player.play(str(wav_path))  # must not raise

        assert any(
            "playback failed" in r.message.lower() and r.levelname == "ERROR"
            for r in caplog.records
        )

    def test_play_never_raises_on_oserror(self, tmp_path, caplog):
        wav_path = tmp_path / "fake.wav"
        wav_path.write_bytes(b"not a real wav")

        with patch("src.sound_player.winsound.PlaySound") as mock_play:
            mock_play.side_effect = OSError("device unavailable")
            player = SoundPlayer()
            player.play(str(wav_path))  # must not raise

        assert any(
            "playback failed" in r.message.lower() and r.levelname == "ERROR"
            for r in caplog.records
        )

    def test_play_never_raises_when_abspath_raises(self, caplog):
        with patch("src.sound_player.os.path.abspath") as mock_abspath:
            mock_abspath.side_effect = OSError("getcwd failed: cwd removed")
            player = SoundPlayer()
            player.play("some/path.wav")  # must not raise

        assert any(
            "playback failed" in r.message.lower() and r.levelname == "ERROR"
            for r in caplog.records
        )


class TestSoundPlayerSuccess:
    def test_play_with_valid_path_calls_winsound(self, tmp_path):
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(b"fake wav bytes")

        with patch("src.sound_player.winsound.PlaySound") as mock_play:
            player = SoundPlayer()
            player.play(str(wav_path))
            mock_play.assert_called_once()
            # Verify SND_ASYNC and SND_FILENAME flags were passed
            call_args = mock_play.call_args
            flags = call_args[0][1]
            assert flags & winsound.SND_ASYNC
            assert flags & winsound.SND_FILENAME
