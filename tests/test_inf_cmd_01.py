import sys
import pytest
from src.backend.utils.file_utils import normalize_path, safe_file_access


def test_max_path_normalization():
    short_path = "C:\\ShortDir\\file.txt"
    norm_short = normalize_path(short_path)
    assert norm_short == short_path

    long_subpath = "a" * 250
    long_path = f"C:\\{long_subpath}\\file.txt"
    norm_long = normalize_path(long_path)

    if sys.platform == "win32":
        assert norm_long.startswith("\\\\?\\")
    else:
        assert norm_long == long_path


def test_permission_error_interceptor(caplog):
    @safe_file_access(default_return=[])
    def restricted_folder_scan(path):
        raise PermissionError("Access is denied")

    result = restricted_folder_scan("C:\\System Volume Information")
    assert result == []
    assert "OS File Exception intercepted" in caplog.text


def test_os_error_interceptor(caplog):
    @safe_file_access(default_return=None)
    def broken_file_read(path):
        raise OSError("Device I/O error")

    result = broken_file_read("C:\\InvalidDevice")
    assert result is None
    assert "Device I/O error" in caplog.text
