"""
Archive module for Shadows File Explorer.

Creates .zip files and extracts .zip and .tar archives. Plain functions with no
Qt dependency; they report progress through a callback and can be cancelled
with a threading.Event, so the UI can run them in a background thread.

Extraction never writes outside the destination folder: entries with absolute
paths or ".." components, and links pointing outside, are refused.
"""
import os
import shutil
import tarfile
import tempfile
import zipfile

from utils import is_within, unique_target_path

TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
ARCHIVE_SUFFIXES = (".zip",) + TAR_SUFFIXES


class ArchiveCancelled(Exception):
    """Raised when the user cancels an archive operation."""


class UnsafeArchiveError(Exception):
    """Raised when an archive tries to write outside the destination folder."""


def is_archive(path):
    """Whether path is an archive this module can extract."""
    lower = path.lower()
    return os.path.isfile(path) and lower.endswith(ARCHIVE_SUFFIXES)


def archive_stem(path):
    """Archive name without its archive extension ("photos.tar.gz" -> "photos")."""
    name = os.path.basename(path)
    lower = name.lower()
    for suffix in sorted(ARCHIVE_SUFFIXES, key=len, reverse=True):
        if lower.endswith(suffix):
            return name[:-len(suffix)] or name
    return os.path.splitext(name)[0]


def suggest_zip_path(sources):
    """A free .zip path next to the sources.

    One item becomes "item.zip"; several become "<parent folder>.zip".
    """
    parent = os.path.dirname(os.path.normpath(sources[0]))
    if len(sources) == 1:
        base = os.path.basename(os.path.normpath(sources[0]))
        if os.path.isfile(sources[0]):
            base = os.path.splitext(base)[0] or base
    else:
        base = os.path.basename(parent) or "Archive"
    return unique_target_path(parent, f"{base}.zip")


def _check(cancel):
    if cancel is not None and cancel.is_set():
        raise ArchiveCancelled()


def _zip_entries(sources):
    """(file path, name inside the zip) for every file and folder in sources."""
    entries = []
    for source in sources:
        source = os.path.normpath(source)
        base = os.path.dirname(source)
        if os.path.isdir(source) and not os.path.islink(source):
            entries.append((source, os.path.relpath(source, base) + "/"))
            for root, dirs, files in os.walk(source):
                dirs.sort()
                for name in dirs:
                    path = os.path.join(root, name)
                    entries.append((path, os.path.relpath(path, base) + "/"))
                for name in sorted(files):
                    path = os.path.join(root, name)
                    entries.append((path, os.path.relpath(path, base)))
        else:
            entries.append((source, os.path.basename(source)))
    return [(path, arcname.replace(os.sep, "/")) for path, arcname in entries]


def create_zip(sources, zip_path, progress=None, cancel=None):
    """Compress files and folders into a new .zip file.

    The archive is written to a temporary file and moved into place at the
    end, so a cancelled or failed run leaves nothing behind.

    Args:
        sources: Files and folders to add
        zip_path: Path of the .zip to create (must not exist)
        progress: Optional callback(done_bytes, total_bytes)
        cancel: Optional threading.Event to stop early
    """
    if os.path.exists(zip_path):
        raise FileExistsError(zip_path)
    entries = _zip_entries(sources)
    total = sum(os.path.getsize(p) for p, arc in entries if not arc.endswith("/")) or 1
    done = 0

    fd, temp_path = tempfile.mkstemp(suffix=".zip.part", dir=os.path.dirname(zip_path) or ".")
    os.close(fd)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, arcname in entries:
                _check(cancel)
                archive.write(path, arcname)
                if not arcname.endswith("/"):
                    done += os.path.getsize(path)
                    if progress:
                        progress(done, total)
        os.replace(temp_path, zip_path)
    except BaseException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    return zip_path


def _safe_target(destination, member_name):
    """The path a member extracts to, refusing anything outside destination."""
    if os.path.isabs(member_name) or member_name.startswith(("/", "\\")):
        raise UnsafeArchiveError(f"Absolute path in archive: {member_name}")
    target = os.path.normpath(os.path.join(destination, member_name))
    if not is_within(target, destination):
        raise UnsafeArchiveError(f"Entry escapes the destination folder: {member_name}")
    return target


def _clean_name(name):
    """Archive member name with "./" prefixes removed and forward slashes."""
    name = name.replace("\\", "/")
    while name.startswith("./"):
        name = name[2:]
    return name.lstrip("/")


def archive_top_level_names(archive_path):
    """Names of the top-level entries in an archive."""
    if archive_path.lower().endswith(".zip"):
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
    else:
        with tarfile.open(archive_path) as archive:
            names = archive.getnames()
    tops = set()
    for name in names:
        top = _clean_name(name).split("/", 1)[0]
        if top:
            tops.add(top)
    return sorted(tops)


def extract_destination(archive_path):
    """Where "Extract" puts an archive's contents.

    An archive holding a single top-level folder is extracted next to the
    archive (unless that folder already exists); anything else goes into a
    new folder named after the archive, so files never spill into the
    current folder.

    Returns:
        tuple: (destination folder, path of the item that will be created)
    """
    parent = os.path.dirname(os.path.abspath(archive_path))
    tops = archive_top_level_names(archive_path)
    if len(tops) == 1 and not os.path.exists(os.path.join(parent, tops[0])):
        single = os.path.join(parent, tops[0])
        if _top_is_folder(archive_path, tops[0]):
            return parent, single
    folder = unique_target_path(parent, archive_stem(archive_path))
    return folder, folder


def _top_is_folder(archive_path, top):
    if archive_path.lower().endswith(".zip"):
        with zipfile.ZipFile(archive_path) as archive:
            return any(_clean_name(name).startswith(top + "/") for name in archive.namelist())
    with tarfile.open(archive_path) as archive:
        return any(_clean_name(member.name).startswith(top + "/") or
                   (_clean_name(member.name) == top and member.isdir()) for member in archive.getmembers())


def extract_archive(archive_path, destination, progress=None, cancel=None):
    """Extract an archive into destination (created if needed).

    Existing files are never overwritten; an archive entry whose target
    already exists raises FileExistsError before anything is written.

    Args:
        archive_path: .zip or .tar archive
        destination: Folder to extract into
        progress: Optional callback(done_entries, total_entries)
        cancel: Optional threading.Event to stop early
    """
    destination = os.path.abspath(destination)
    created_destination = not os.path.exists(destination)
    os.makedirs(destination, exist_ok=True)
    try:
        if archive_path.lower().endswith(".zip"):
            _extract_zip(archive_path, destination, progress, cancel)
        else:
            _extract_tar(archive_path, destination, progress, cancel)
    except BaseException:
        if created_destination:
            shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination


def _extract_zip(archive_path, destination, progress, cancel):
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        targets = [_safe_target(destination, m.filename) for m in members]
        for member, target in zip(members, targets):
            if not member.is_dir() and os.path.exists(target):
                raise FileExistsError(target)
        for i, (member, target) in enumerate(zip(members, targets)):
            _check(cancel)
            if member.is_dir():
                os.makedirs(target, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive.open(member) as source, open(target, "wb") as out:
                    shutil.copyfileobj(source, out)
            if progress:
                progress(i + 1, len(members))


def _extract_tar(archive_path, destination, progress, cancel):
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        for member in members:
            target = _safe_target(destination, member.name)
            if member.issym() or member.islnk():
                link_base = os.path.dirname(target) if member.issym() else destination
                _safe_target(destination, os.path.relpath(
                    os.path.normpath(os.path.join(link_base, member.linkname)), destination))
            elif not (member.isfile() or member.isdir()):
                raise UnsafeArchiveError(f"Unsupported entry type in archive: {member.name}")
            if not member.isdir() and os.path.lexists(target):
                raise FileExistsError(target)
        for i, member in enumerate(members):
            _check(cancel)
            if hasattr(tarfile, "data_filter"):
                archive.extract(member, destination, filter="data")
            else:
                archive.extract(member, destination)
            if progress:
                progress(i + 1, len(members))
