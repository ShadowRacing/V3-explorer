import threading
import time
from datetime import date, datetime

from PyQt6.QtCore import Qt

from file_searcher import FileSearcher, passes_filters, remove_nested_locations


def test_type_filter():
    assert passes_filters("a.png", False, 1, None, {"type_filter": "images"})
    assert not passes_filters("a.txt", False, 1, None, {"type_filter": "images"})
    assert not passes_filters("pics", True, 0, None, {"type_filter": "images"})
    assert passes_filters("pics", True, 0, None, {"type_filter": "folders"})
    assert not passes_filters("a.png", False, 1, None, {"type_filter": "folders"})


def test_size_filter_skips_directories():
    options = {"size_filter": (100, None)}
    assert not passes_filters("small", False, 10, None, options)
    assert passes_filters("big", False, 1000, None, options)
    assert passes_filters("dir", True, 0, None, options)


def test_date_filter():
    mtime = datetime(2024, 6, 1, 12).timestamp()
    assert passes_filters("f", False, 0, mtime, {"date_filter": ("after", date(2024, 1, 1))})
    assert not passes_filters("f", False, 0, mtime, {"date_filter": ("before", date(2024, 1, 1))})


def test_remove_nested_locations(tmp_path):
    outer, inner = str(tmp_path), str(tmp_path / "x")
    assert remove_nested_locations([inner, outer, outer]) == [outer]


def _run_search(searcher, timeout=10):
    results, done = [], threading.Event()
    lock = threading.Lock()

    def collect(result):
        with lock:
            results.append(result)

    # Direct connections: the test has no event loop to deliver queued signals
    direct = Qt.ConnectionType.DirectConnection
    searcher.found_item.connect(collect, direct)
    searcher.finished.connect(lambda _id: done.set(), direct)
    assert searcher.start_search()
    assert done.wait(timeout)
    return results


def test_search_finds_files_and_folders(qapp, tmp_path):
    (tmp_path / "match_dir").mkdir()
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "Match.txt").write_text("x")
    (tmp_path / "other.txt").write_text("x")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "match_hidden.txt").write_text("x")

    searcher = FileSearcher()
    searcher.configure_search([str(tmp_path)], "match")
    names = sorted(r.filename for r in _run_search(searcher))
    assert names == ["Match.txt", "match_dir"]


def test_non_recursive_search(qapp, tmp_path):
    (tmp_path / "match_top.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "match_deep.txt").write_text("x")

    searcher = FileSearcher()
    searcher.configure_search(str(tmp_path), "match", {"include_subfolders": False})
    assert [r.filename for r in _run_search(searcher)] == ["match_top.txt"]


def test_new_search_gets_new_id(qapp, tmp_path):
    searcher = FileSearcher()
    searcher.configure_search(str(tmp_path), "x")
    _run_search(searcher)
    first = searcher.search_id
    searcher.configure_search(str(tmp_path), "y")
    searcher.start_search()
    assert searcher.search_id == first + 1
    searcher.stop()
    deadline = time.time() + 5
    while searcher.is_running and time.time() < deadline:
        time.sleep(0.01)
    assert not searcher.is_running
