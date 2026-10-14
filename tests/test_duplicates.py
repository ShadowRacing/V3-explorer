import os
import threading

import pytest

from shadows_explorer.core.duplicates import (PARTIAL_BYTES, DuplicateScanCancelled, extra_copies,
                                              find_duplicates)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def test_finds_identical_files_only(tmp_path):
    a = write(tmp_path / "a.txt", b"hello world")
    b = write(tmp_path / "sub" / "b.txt", b"hello world")
    write(tmp_path / "c.txt", b"hello WORLD")  # Same size, different content
    write(tmp_path / "d.txt", b"unique")
    write(tmp_path / "empty1", b"")
    write(tmp_path / "empty2", b"")  # Empty files are ignored
    groups = find_duplicates([str(tmp_path)])
    assert [g.paths for g in groups] == [sorted([a, b])]
    assert groups[0].wasted == 11


def test_large_files_differing_after_partial_hash(tmp_path):
    same = b"x" * (PARTIAL_BYTES + 10)
    a = write(tmp_path / "a.bin", same)
    b = write(tmp_path / "b.bin", same)
    write(tmp_path / "c.bin", b"x" * PARTIAL_BYTES + b"y" * 10)  # Same start, different end
    groups = find_duplicates([str(tmp_path)])
    assert [g.paths for g in groups] == [sorted([a, b])]


def test_sorted_by_wasted_space_and_min_size(tmp_path):
    write(tmp_path / "s1", b"ab")
    write(tmp_path / "s2", b"ab")
    write(tmp_path / "b1", b"x" * 100)
    write(tmp_path / "b2", b"x" * 100)
    write(tmp_path / "b3", b"x" * 100)
    groups = find_duplicates([str(tmp_path)])
    assert [len(g.paths) for g in groups] == [3, 2]
    assert len(find_duplicates([str(tmp_path)], min_size=10)) == 1


def test_hard_links_are_not_duplicates(tmp_path):
    a = write(tmp_path / "a.txt", b"same data")
    try:
        os.link(a, tmp_path / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("hard links not available")
    assert find_duplicates([str(tmp_path)]) == []


def test_hidden_files_are_optional(tmp_path):
    write(tmp_path / "a.txt", b"data")
    write(tmp_path / ".hidden" / "a.txt", b"data")
    assert find_duplicates([str(tmp_path)]) == []
    assert len(find_duplicates([str(tmp_path)], include_hidden=True)) == 1


def test_extra_copies_keeps_one(tmp_path):
    old = write(tmp_path / "old.txt", b"data")
    new = write(tmp_path / "deeper" / "new.txt", b"data")
    os.utime(old, (1000, 1000))
    group = find_duplicates([str(tmp_path)])[0]
    assert extra_copies(group, "oldest") == [new]
    assert extra_copies(group, "newest") == [old]
    assert extra_copies(group, "shortest") == [new]


def test_cancel(tmp_path):
    write(tmp_path / "a", b"1")
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(DuplicateScanCancelled):
        find_duplicates([str(tmp_path)], cancel=cancel)
