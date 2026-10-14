from datetime import date, datetime

from grouping import Entry, date_group, group_entries, list_entries, sort_entries

TODAY = date(2026, 10, 14)  # A Wednesday


def ts(year, month, day):
    return datetime(year, month, day, 12).timestamp()


def entry(name, is_dir=False, size=0, mtime=None):
    return Entry(name, "/x/" + name, is_dir, size, mtime or ts(2026, 10, 14))


def test_date_groups():
    assert date_group(ts(2026, 10, 14), TODAY) == "Today"
    assert date_group(ts(2026, 10, 13), TODAY) == "Yesterday"
    assert date_group(ts(2026, 10, 12), TODAY) == "Earlier this week"  # Monday
    assert date_group(ts(2026, 10, 7), TODAY) == "Last week"
    assert date_group(ts(2026, 10, 2), TODAY) == "Earlier this month"
    assert date_group(ts(2026, 9, 20), TODAY) == "Last month"
    assert date_group(ts(2026, 3, 1), TODAY) == "Earlier this year"
    assert date_group(ts(2020, 1, 1), TODAY) == "A long time ago"
    assert date_group(ts(2027, 1, 1), TODAY) == "In the future"
    # January: last month is December of the previous year
    assert date_group(ts(2026, 12, 20), date(2027, 1, 20)) == "Last month"


def test_sort_keeps_folders_first():
    entries = [entry("b.txt", size=5), entry("Zeta", is_dir=True), entry("a.txt", size=50)]
    assert [e.name for e in sort_entries(entries, "name")] == ["Zeta", "a.txt", "b.txt"]
    assert [e.name for e in sort_entries(entries, "size", descending=True)] == ["Zeta", "a.txt", "b.txt"]
    assert [e.name for e in sort_entries(entries, "name", descending=True)] == ["Zeta", "b.txt", "a.txt"]


def test_group_by_type_in_explorer_order():
    entries = [entry("song.mp3"), entry("photo.jpg"), entry("Docs", is_dir=True), entry("notes.txt"),
               entry("data.bin")]
    groups = group_entries(entries, "type")
    assert [name for name, _ in groups] == ["Folders", "Documents", "Pictures", "Music", "Other files"]


def test_group_by_size_and_none():
    entries = [entry("empty.txt", size=0), entry("big.iso", size=2 * 1024 ** 3), entry("Dir", is_dir=True)]
    assert [(name, [e.name for e in items]) for name, items in group_entries(entries, "size")] == [
        ("Folders", ["Dir"]), ("Empty", ["empty.txt"]), ("Huge (1 - 4 GB)", ["big.iso"])]
    assert group_entries(entries, "none") == [("", entries)]


def test_list_entries_skips_hidden(tmp_path):
    (tmp_path / "shown.txt").write_text("abc")
    (tmp_path / ".hidden").write_text("x")
    (tmp_path / "folder").mkdir()
    names = sorted(e.name for e in list_entries(str(tmp_path)))
    assert names == ["folder", "shown.txt"]
    assert len(list_entries(str(tmp_path), show_hidden=True)) == 3
