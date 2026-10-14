import os

from shadows_explorer.core.grouping import Entry, group_entries
from shadows_explorer.core.query import parse_query
from shadows_explorer.core.search import FileSearcher
from shadows_explorer.core.tags import DEFAULT_TAGS, TagStore

from test_file_searcher import _run_search


def test_tagging_and_order(tmp_path):
    store = TagStore()
    a = str(tmp_path / "a.txt")
    store.set_tag([a], "Blue")
    store.set_tag([a], "Red")
    assert store.tags_for(a) == ["Red", "Blue"]  # Display order, not the order they were added
    assert store.colors_for(a) == ["#ef4444", "#3b82f6"]
    store.set_tag([a], "Red", on=False)
    assert store.tags_for(a) == ["Blue"]
    store.clear([a])
    assert store.tags_for(a) == [] and store.items == {}


def test_paths_keep_their_spelling(tmp_path):
    store = TagStore()
    path = str(tmp_path / "My Photos" / "Beach.JPG")
    store.set_tag([path], "Red")
    assert store.paths_with("Red") == [path]
    store.move([(str(tmp_path / "My Photos"), str(tmp_path / "Holiday"))])
    assert store.paths_with("Red") == [str(tmp_path / "Holiday" / "Beach.JPG")]


def test_toggle_applies_to_all_unless_all_have_it(tmp_path):
    store = TagStore()
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    store.set_tag([a], "Green")
    assert store.toggle_tag([a, b], "Green") is True
    assert store.tags_for(b) == ["Green"]
    assert store.toggle_tag([a, b], "Green") is False
    assert store.tags_for(a) == store.tags_for(b) == []


def test_saved_and_loaded(tmp_path):
    file_path = str(tmp_path / "data" / "tags.json")
    store = TagStore(file_path)
    store.create_tag("Work", "#14b8a6")
    store.set_tag([str(tmp_path / "x")], "Work")
    loaded = TagStore(file_path)
    assert list(loaded.tags)[-1] == "Work"
    assert loaded.tags_for(str(tmp_path / "x")) == ["Work"]
    with open(file_path, "w") as f:
        f.write("{broken")
    assert TagStore(file_path).tags == dict(DEFAULT_TAGS)


def test_tag_definitions(tmp_path):
    store = TagStore()
    a = str(tmp_path / "a")
    assert store.create_tag("Work", "#000000")
    assert not store.create_tag("work", "#111111")  # Names are case-insensitive
    store.set_tag([a], "Work")
    assert not store.rename_tag("Work", "red")
    assert store.rename_tag("Work", "Job")
    assert store.tags_for(a) == ["Job"]
    store.set_color("Job", "#123456")
    assert store.colors_for(a) == ["#123456"]
    assert store.find_tag("JOB") == "Job"
    store.delete_tag("Job")
    assert store.tags_for(a) == [] and "Job" not in store.tags
    assert store.counts()["Red"] == 0


def test_tags_follow_moves_and_renames(tmp_path):
    store = TagStore()
    folder = tmp_path / "folder"
    inside = folder / "sub" / "file.txt"
    store.set_tag([str(folder)], "Red")
    store.set_tag([str(inside)], "Blue")
    store.set_tag([str(tmp_path / "folder2")], "Green")  # Shares a prefix, must not move
    store.move([(str(folder), str(tmp_path / "renamed"))])
    assert store.tags_for(str(tmp_path / "renamed")) == ["Red"]
    assert store.tags_for(str(tmp_path / "renamed" / "sub" / "file.txt")) == ["Blue"]
    assert store.tags_for(str(folder)) == []
    assert store.tags_for(str(tmp_path / "folder2")) == ["Green"]

    # Swapping two names keeps each file's own tags
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    store.set_tag([a], "Red")
    store.set_tag([b], "Blue")
    store.move([(a, b), (b, a)])
    assert store.tags_for(a) == ["Blue"] and store.tags_for(b) == ["Red"]


def test_forget_and_prune(tmp_path):
    store = TagStore()
    folder = tmp_path / "f"
    folder.mkdir()
    (folder / "keep.txt").write_text("x")
    store.set_tag([str(folder / "keep.txt")], "Red")
    store.set_tag([str(folder / "gone.txt")], "Red")
    assert store.prune_missing() == 1
    assert store.paths_with("Red") == [str(folder / "keep.txt")]
    store.forget([str(folder)])
    assert store.paths_with("Red") == []


def test_tag_query_and_grouping(qapp, tmp_path):
    store = TagStore()
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    (tmp_path / "c.txt").write_text("x")
    store.set_tag([str(tmp_path / "a.txt")], "Red")
    store.set_tag([str(tmp_path / "b.txt")], "Red")
    store.set_tag([str(tmp_path / "b.txt")], "Blue")

    query = parse_query("tag:red -tag:blue")
    assert query.matches_tags(["red"]) and not query.matches_tags(["red", "blue"])
    assert not query.is_empty()

    searcher = FileSearcher()
    searcher.tag_lookup = lambda path: [t.lower() for t in store.tags_for(path)]
    searcher.configure_search(str(tmp_path), "tag:red")
    assert sorted(r.filename for r in _run_search(searcher)) == ["a.txt", "b.txt"]

    entries = [Entry(n, str(tmp_path / n), False, 1, 0) for n in ("a.txt", "b.txt", "c.txt")]
    groups = group_entries(entries, "tag", tags_of=store.tags_for, tag_order=list(store.tags))
    assert [(name, [e.name for e in items]) for name, items in groups] == [
        ("Red", ["a.txt", "b.txt"]), ("Blue", ["b.txt"]), ("No tags", ["c.txt"])]
    assert os.path.exists(str(tmp_path / "c.txt"))
