import os
from src.file_writer import FileWriter


class TestFileWriterOutput:
    def test_write_time(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_time(0, "04:23")
        assert open(path).read() == "04:23"

    def test_write_end_message(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_end_message(0, "TIME'S UP")
        assert open(path).read() == "TIME'S UP"

    def test_clear_file(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_time(0, "04:23")
        fw.clear(0)
        assert open(path).read() == ""

    def test_write_blank_end_message(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_end_message(0, "")
        assert open(path).read() == ""

    def test_creates_output_directory(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "subdir" / "timer.txt")
        fw.register(0, path)
        fw.write_time(0, "01:00")
        assert os.path.exists(path)


class TestFileWriterEnforcement:
    def test_rejects_duplicate_path(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        try:
            fw.register(1, path)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "already assigned" in str(e)

    def test_allows_same_timer_reregister(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.register(0, str(tmp_path / "other.txt"))
        fw.write_time(0, "01:00")
        assert open(str(tmp_path / "other.txt")).read() == "01:00"

    def test_unregister_frees_path(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.unregister(0)
        fw.register(1, path)
        fw.write_time(1, "05:00")
        assert open(path).read() == "05:00"


class TestFileWriterAtomicWrite:
    def test_no_temp_file_left_behind(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_time(0, "04:23")
        files = os.listdir(str(tmp_path))
        assert files == ["timer.txt"]
