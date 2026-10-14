import os

from utils import (NavigationHistory, format_size, is_valid_filename, is_within,
                   normalize_path, paths_equal, unique_target_path)


def test_format_size():
    assert format_size(0) == "0 bytes"
    assert format_size(1) == "1 byte"
    assert format_size(1023) == "1023 bytes"
    assert format_size(1536) == "1.5 KB"
    assert format_size(5 * 1024 ** 2) == "5.0 MB"
    assert format_size(3 * 1024 ** 4) == "3072.0 GB"


def test_normalize_path_windows_keeps_full_path():
    # Regression: C:\Users\x used to be truncated to C:\
    assert normalize_path("C:\\Users\\wim", is_windows=True) == "C:\\Users\\wim"
    assert normalize_path("C:/Users/wim", is_windows=True) == "C:\\Users\\wim"
    assert normalize_path("C:", is_windows=True) == "C:\\"
    assert normalize_path("D:/", is_windows=True) == "D:\\"


def test_normalize_path_posix_unchanged():
    assert normalize_path("/home/user", is_windows=False) == "/home/user"


def test_is_within_is_not_a_prefix_match(tmp_path):
    etc = tmp_path / "etc"
    assert is_within(str(etc / "passwd"), str(etc))
    assert is_within(str(etc), str(etc))
    assert not is_within(str(tmp_path / "etcetera"), str(etc))


def test_paths_equal():
    assert paths_equal("/a/b/", "/a/b")
    assert not paths_equal("/a/b", "/a/c")
    assert not paths_equal("", "/a")


def test_unique_target_path(tmp_path):
    assert unique_target_path(str(tmp_path), "a.txt") == str(tmp_path / "a.txt")
    (tmp_path / "a.txt").write_text("x")
    assert unique_target_path(str(tmp_path), "a.txt") == str(tmp_path / "a (1).txt")
    (tmp_path / "a (1).txt").write_text("x")
    assert unique_target_path(str(tmp_path), "a.txt") == str(tmp_path / "a (2).txt")


def test_unique_target_path_folder_with_dot(tmp_path):
    (tmp_path / "v1.2").mkdir()
    assert unique_target_path(str(tmp_path), "v1.2") == str(tmp_path / "v1.2 (1)")


def test_is_valid_filename():
    assert is_valid_filename("report.txt")
    for bad in ("", ".", "..", "a/b", " padded", "nul\0"):
        assert not is_valid_filename(bad)


def test_history_back_goes_to_previous_folder():
    # Regression: Home -> A -> B, Back used to land on Home instead of A
    history = NavigationHistory()
    for path in ("/home", "/a", "/b"):
        history.visit(path)
    assert history.back() == "/a"
    assert history.back() == "/home"
    assert history.back() is None
    assert history.forward() == "/a"


def test_history_visit_drops_forward_entries():
    history = NavigationHistory()
    for path in ("/1", "/2", "/3"):
        history.visit(path)
    history.back()
    history.visit("/4")
    assert history.entries == ["/1", "/2", "/4"]
    assert not history.can_go_forward()


def test_history_ignores_repeat_visit():
    history = NavigationHistory()
    history.visit("/1")
    history.visit("/1" + os.sep)
    assert history.entries == ["/1"]
