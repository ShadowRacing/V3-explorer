import os
import threading

import pytest

from shadows_explorer.core.disk_usage import ScanCancelled, folder_size, largest_files, scan


def make_tree(root):
    (root / "a" / "deep").mkdir(parents=True)
    (root / "a" / "deep" / "big.bin").write_bytes(b"x" * 5000)
    (root / "a" / "small.txt").write_bytes(b"x" * 10)
    (root / "b").mkdir()
    (root / "b" / "mid.bin").write_bytes(b"x" * 300)
    (root / "top.txt").write_bytes(b"x" * 20)


def test_folder_size(tmp_path):
    make_tree(tmp_path)
    assert folder_size(str(tmp_path)) == (5330, 4, 3)


def test_scan_sums_sizes_and_sorts(tmp_path):
    make_tree(tmp_path)
    root = scan(str(tmp_path))
    assert root.size == 5330 and root.files == 4
    assert [c.name for c in root.sorted_children()] == ["a", "b", "top.txt"]
    a = next(c for c in root.children if c.name == "a")
    assert a.size == 5010 and a.files == 2
    assert [f.name for f in largest_files(root, 2)] == ["big.bin", "mid.bin"]


def test_scan_does_not_follow_symlinks(tmp_path):
    make_tree(tmp_path)
    try:
        os.symlink(tmp_path, tmp_path / "loop", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    # A followed link would loop forever or count everything twice
    assert scan(str(tmp_path)).size < 2 * 5330


def test_scan_can_be_cancelled(tmp_path):
    make_tree(tmp_path)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ScanCancelled):
        scan(str(tmp_path), cancel=cancel)


def test_unreadable_folder_is_skipped(tmp_path):
    assert scan(str(tmp_path / "missing")).size == 0
