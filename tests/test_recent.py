import fnmatch

from recent import MAX_FOLDERS, RecentItems, filter_pattern


class FakeSettings(dict):
    def value(self, key, default=None):
        return self.get(key, default)

    def setValue(self, key, value):
        self[key] = value


def test_recent_files_newest_first_without_duplicates(tmp_path):
    settings = FakeSettings()
    recent = RecentItems(settings)
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("a")
    b.write_text("b")
    recent.add_file(str(a))
    recent.add_file(str(b))
    recent.add_file(str(a))
    assert recent.existing_files() == [str(a), str(b)]

    # Persisted and reloaded
    assert RecentItems(settings).existing_files() == [str(a), str(b)]

    b.unlink()
    assert recent.existing_files() == [str(a)]  # Missing files are skipped


def test_recent_folders_are_capped_and_clearable(tmp_path):
    recent = RecentItems(FakeSettings())
    for i in range(MAX_FOLDERS + 5):
        folder = tmp_path / f"d{i}"
        folder.mkdir()
        recent.add_folder(str(folder))
    assert len(recent.folders) == MAX_FOLDERS
    assert recent.existing_folders()[0] == str(tmp_path / f"d{MAX_FOLDERS + 4}")
    recent.remove(str(tmp_path / f"d{MAX_FOLDERS + 4}"))
    assert recent.existing_folders()[0] == str(tmp_path / f"d{MAX_FOLDERS + 3}")
    recent.clear()
    assert recent.existing_folders() == [] and recent.existing_files() == []


def test_corrupt_settings_are_ignored():
    assert RecentItems(FakeSettings(recent_files="not json")).files == []


def test_filter_pattern():
    assert filter_pattern("") == ""
    assert filter_pattern(" rep ") == "*rep*"
    assert filter_pattern("*.jpg") == "*.jpg"
    pattern = filter_pattern("[draft]")
    assert fnmatch.fnmatch("my [draft] notes.txt", pattern)
    assert not fnmatch.fnmatch("my d notes.txt", pattern)
