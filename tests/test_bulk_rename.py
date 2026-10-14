import os

import pytest

from shadows_explorer.core.bulk_rename import RenameOptions, execute_renames, find_problems, new_name_for, plan_renames


def test_find_replace_keeps_extension():
    options = RenameOptions(find="IMG", replace="Photo")
    assert new_name_for("img_001.IMG.jpg", 0, options) == "Photo_001.Photo.jpg"
    assert new_name_for("img.img", 0, options) == "Photo.img"  # extension untouched
    assert new_name_for("img.img", 0, RenameOptions(find="img", replace="x", include_extension=True)) == "x.x"


def test_case_sensitive_and_regex():
    assert new_name_for("Aa.txt", 0, RenameOptions(find="a", replace="b", case_sensitive=True)) == "Ab.txt"
    options = RenameOptions(find=r"(\d+)-(\d+)", replace=r"\2-\1", use_regex=True)
    assert new_name_for("2024-06.csv", 0, options) == "06-2024.csv"
    # Without regex, backslashes and dots are literal
    assert new_name_for("a.b.c.txt", 0, RenameOptions(find=".", replace="\\1")) == "a\\1b\\1c.txt"


def test_template_numbering():
    options = RenameOptions(template="Holiday {n}", start=7, padding=3)
    assert [new_name_for("x.jpg", i, options) for i in range(2)] == ["Holiday 007.jpg", "Holiday 008.jpg"]
    assert new_name_for("beach.jpg", 0, RenameOptions(template="{n} - {name}")) == "1 - beach.jpg"


def test_prefix_suffix_and_case():
    options = RenameOptions(prefix="old_", suffix="_v2", case="upper")
    assert new_name_for("Report.docx", 0, options) == "OLD_REPORT_V2.docx"
    assert new_name_for("my notes.md", 0, RenameOptions(case="title")) == "My Notes.md"


def test_folders_have_no_extension(tmp_path):
    (tmp_path / "v1.2").mkdir()
    assert plan_renames([str(tmp_path / "v1.2")], RenameOptions(suffix="-old")) == \
        [(str(tmp_path / "v1.2"), "v1.2-old")]


def test_problems(tmp_path):
    for name in ("a.txt", "b.txt", "keep.txt"):
        (tmp_path / name).write_text(name)
    a, b = str(tmp_path / "a.txt"), str(tmp_path / "b.txt")
    assert find_problems([(a, "same.txt"), (b, "same.txt")]) == {a: "Duplicate name", b: "Duplicate name"}
    assert find_problems([(a, "keep.txt")]) == {a: "Name already exists"}
    assert find_problems([(a, "bad/name.txt")]) == {a: "Invalid name"}
    # Taking a name that is itself being renamed away is fine (a swap)
    assert find_problems([(a, "b.txt"), (b, "a.txt")]) == {}


def test_execute_swaps_names(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "b.txt").write_text("B")
    a, b = str(tmp_path / "a.txt"), str(tmp_path / "b.txt")
    applied = execute_renames([(a, b), (b, a)])
    assert len(applied) == 2
    assert (tmp_path / "a.txt").read_text() == "B" and (tmp_path / "b.txt").read_text() == "A"
    assert sorted(os.listdir(tmp_path)) == ["a.txt", "b.txt"]


def test_execute_rolls_back_on_failure(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "taken.txt").write_text("T")
    with pytest.raises(FileExistsError):
        execute_renames([(str(tmp_path / "a.txt"), str(tmp_path / "taken.txt"))])
    assert sorted(os.listdir(tmp_path)) == ["a.txt", "taken.txt"]
    assert (tmp_path / "a.txt").read_text() == "A"
