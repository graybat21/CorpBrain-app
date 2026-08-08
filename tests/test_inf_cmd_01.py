import os
import sys

import pytest

from src.backend.utils.file_utils import normalize_path, safe_file_access

# MAX_PATH and the `\\?\` extended-length prefix are Windows concepts. The assertions that
# depend on them can only be made on Windows: off Windows, `os.path.abspath` treats
# "C:\ShortDir\file.txt" as a *relative* single-segment filename and prepends the CWD, so a
# test feeding it Windows path strings asserts nothing about the shipped behaviour.
#
# Rather than weaken the assertions to something that passes everywhere, the Windows ones are
# skipped off Windows (CI runs windows-latest, where they are the real check) and a separate
# POSIX test fixes the property that matters on a dev host: the guard holds, so no `\\?\`
# prefix is ever emitted there.
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="MAX_PATH / \\\\?\\ is Windows-only")


@windows_only
def test_max_path_normalization_leaves_short_paths_alone():
    short_path = "C:\\ShortDir\\file.txt"
    assert normalize_path(short_path) == short_path


@windows_only
def test_max_path_normalization_prefixes_long_paths():
    long_path = f"C:\\{'a' * 250}\\file.txt"
    assert normalize_path(long_path).startswith("\\\\?\\")


@windows_only
def test_max_path_normalization_prefixes_long_unc_paths():
    # UNC gets a different prefix form: \\server\share -> \\?\UNC\server\share
    long_unc = f"\\\\fileserver\\share\\{'a' * 250}\\file.txt"
    assert normalize_path(long_unc).startswith("\\\\?\\UNC\\")


@pytest.mark.skipif(sys.platform == "win32", reason="asserts the non-Windows branch")
def test_normalize_path_adds_no_windows_prefix_off_windows(tmp_path):
    long_posix = str(tmp_path / ("a" * 250) / "file.txt")
    normalized = normalize_path(long_posix)

    assert not normalized.startswith("\\\\?\\")
    assert os.path.isabs(normalized)
    assert normalized == os.path.abspath(long_posix)


def test_normalize_path_returns_empty_input_unchanged():
    assert normalize_path("") == ""


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
