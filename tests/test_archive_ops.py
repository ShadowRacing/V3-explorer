import io
import os
import tarfile
import threading
import zipfile

import pytest

from shadows_explorer.core.archive import (ArchiveCancelled, UnsafeArchiveError, archive_stem, create_zip,
                         extract_archive, extract_destination, is_archive, suggest_zip_path)


def make_tree(root):
    (root / "docs" / "sub").mkdir(parents=True)
    (root / "docs" / "a.txt").write_text("alpha")
    (root / "docs" / "sub" / "b.txt").write_text("beta")
    (root / "single.txt").write_text("one")


def test_zip_and_extract_round_trip(tmp_path):
    make_tree(tmp_path)
    zip_path = str(tmp_path / "out.zip")
    calls = []
    create_zip([str(tmp_path / "docs"), str(tmp_path / "single.txt")], zip_path,
               progress=lambda done, total: calls.append((done, total)))
    assert calls and calls[-1][0] == calls[-1][1]
    with zipfile.ZipFile(zip_path) as archive:
        assert set(archive.namelist()) == {"docs/", "docs/sub/", "docs/a.txt", "docs/sub/b.txt", "single.txt"}

    dest = tmp_path / "extracted"
    extract_archive(zip_path, str(dest))
    assert (dest / "docs" / "sub" / "b.txt").read_text() == "beta"
    assert (dest / "single.txt").read_text() == "one"


def test_create_zip_refuses_existing_and_cleans_up_on_cancel(tmp_path):
    make_tree(tmp_path)
    zip_path = tmp_path / "out.zip"
    zip_path.write_text("existing")
    with pytest.raises(FileExistsError):
        create_zip([str(tmp_path / "docs")], str(zip_path))

    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ArchiveCancelled):
        create_zip([str(tmp_path / "docs")], str(tmp_path / "new.zip"), cancel=cancel)
    assert not (tmp_path / "new.zip").exists()
    assert not [p for p in os.listdir(tmp_path) if p.endswith(".part")]


def test_suggest_zip_path(tmp_path):
    make_tree(tmp_path)
    assert suggest_zip_path([str(tmp_path / "single.txt")]) == str(tmp_path / "single.zip")
    assert suggest_zip_path([str(tmp_path / "docs")]) == str(tmp_path / "docs.zip")
    (tmp_path / "docs.zip").write_text("x")
    assert suggest_zip_path([str(tmp_path / "docs")]) == str(tmp_path / "docs (1).zip")
    both = suggest_zip_path([str(tmp_path / "docs"), str(tmp_path / "single.txt")])
    assert both == str(tmp_path / f"{tmp_path.name}.zip")


def test_archive_names(tmp_path):
    assert archive_stem("/x/photos.tar.gz") == "photos"
    assert archive_stem("/x/a.b.zip") == "a.b"
    (tmp_path / "a.zip").write_bytes(b"")
    (tmp_path / "a.txt").write_text("")
    assert is_archive(str(tmp_path / "a.zip"))
    assert not is_archive(str(tmp_path / "a.txt"))


def test_extract_destination(tmp_path):
    make_tree(tmp_path)
    folder_zip = str(tmp_path / "docs.zip")
    create_zip([str(tmp_path / "docs")], folder_zip)
    # One top-level folder that already exists next to it: use a new folder instead
    assert extract_destination(folder_zip) == (str(tmp_path / "docs (1)"), str(tmp_path / "docs (1)"))

    loose = tmp_path / "loose"
    loose.mkdir()
    loose_zip = str(loose / "files.zip")
    create_zip([str(tmp_path / "single.txt"), str(tmp_path / "docs" / "a.txt")], loose_zip)
    assert extract_destination(loose_zip) == (str(loose / "files"), str(loose / "files"))

    moved = tmp_path / "elsewhere"
    moved.mkdir()
    os.replace(folder_zip, moved / "docs.zip")
    assert extract_destination(str(moved / "docs.zip")) == (str(moved), str(moved / "docs"))


def test_zip_slip_is_refused(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as archive:
        archive.writestr("../escaped.txt", "bad")
    with pytest.raises(UnsafeArchiveError):
        extract_archive(str(evil), str(tmp_path / "dest"))
    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "dest").exists()  # Nothing left behind


def test_tar_symlink_escape_is_refused(tmp_path):
    evil = tmp_path / "evil.tar"
    with tarfile.open(evil, "w") as archive:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        archive.addfile(link)
    with pytest.raises(UnsafeArchiveError):
        extract_archive(str(evil), str(tmp_path / "dest"))


def test_extract_never_overwrites(tmp_path):
    archive_path = tmp_path / "a.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("note.txt", "from zip")
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "note.txt").write_text("mine")
    with pytest.raises(FileExistsError):
        extract_archive(str(archive_path), str(dest))
    assert (dest / "note.txt").read_text() == "mine"


def test_extract_tar_gz(tmp_path):
    archive_path = tmp_path / "data.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        payload = b"hello"
        info = tarfile.TarInfo("data/hello.txt")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    dest, created = extract_destination(str(archive_path))
    extract_archive(str(archive_path), dest)
    assert (tmp_path / "data" / "hello.txt").read_bytes() == b"hello"
    assert created == str(tmp_path / "data")
