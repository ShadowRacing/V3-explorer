"""
Duplicate finder for Shadows File Explorer.

Finds files with identical content under one or more folders, without Qt.
Work is done in increasing cost so most files are never read in full:
1. group by size (files of different size can't be equal)
2. compare a hash of the first 64 KB
3. compare a hash of the whole file

Hard links to the same file are counted once (deleting one frees nothing),
symlinks are not followed, and empty files are ignored.
"""
import hashlib
import os
import time
from dataclasses import dataclass

PARTIAL_BYTES = 64 * 1024
CHUNK_BYTES = 1024 * 1024


class DuplicateScanCancelled(Exception):
    """Raised when a duplicate scan is cancelled."""


@dataclass
class DuplicateGroup:
    """Files that all have the same content."""
    size: int
    paths: list

    @property
    def wasted(self):
        """Bytes freed by keeping only one copy."""
        return self.size * (len(self.paths) - 1)


def _hash(path, limit=None):
    digest = hashlib.blake2b(digest_size=20)
    remaining = limit
    with open(path, "rb") as f:
        while remaining is None or remaining > 0:
            chunk = f.read(CHUNK_BYTES if remaining is None else min(CHUNK_BYTES, remaining))
            if not chunk:
                break
            digest.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return digest.digest()


def _files_by_size(roots, min_size, include_hidden, check):
    """{size: [paths]} for every regular file, one path per physical file."""
    by_size, seen_inodes = {}, set()
    stack = list(roots)
    while stack:
        check()
        try:
            with os.scandir(stack.pop()) as entries:
                for entry in entries:
                    if not include_hidden and entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        stats = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stats.st_size < max(1, min_size):
                        continue
                    inode = (stats.st_dev, stats.st_ino)
                    if stats.st_ino and inode in seen_inodes:
                        continue  # Another hard link to a file we already have
                    seen_inodes.add(inode)
                    by_size.setdefault(stats.st_size, []).append(entry.path)
        except OSError:
            continue
    return by_size


def _split_by_hash(paths, limit, check):
    groups = {}
    for path in paths:
        check()
        try:
            groups.setdefault(_hash(path, limit), []).append(path)
        except OSError:
            continue  # Unreadable files can't be confirmed as duplicates
    return [group for group in groups.values() if len(group) > 1]


def find_duplicates(roots, min_size=1, include_hidden=False, progress=None, cancel=None):
    """Find groups of files with identical content.
    
    Args:
        roots: Folders to search (subfolders included)
        min_size: Ignore files smaller than this many bytes (at least 1)
        include_hidden: Also look at names starting with "."
        progress: Optional callback(done, total) while comparing candidates
        cancel: Optional threading.Event; raises DuplicateScanCancelled when set
        
    Returns:
        list: DuplicateGroup objects, most wasted space first
    """
    def check():
        if cancel is not None and cancel.is_set():
            raise DuplicateScanCancelled()
    
    candidates = [(size, paths) for size, paths in
                  _files_by_size(roots, min_size, include_hidden, check).items() if len(paths) > 1]
    total = sum(len(paths) for _, paths in candidates)
    done, last_report = 0, 0.0
    result = []
    for size, paths in candidates:
        for partial_group in _split_by_hash(paths, PARTIAL_BYTES, check):
            # Files that fit in the partial hash are already fully compared
            full_groups = [partial_group] if size <= PARTIAL_BYTES else _split_by_hash(partial_group, None, check)
            result.extend(DuplicateGroup(size, sorted(group)) for group in full_groups)
        done += len(paths)
        if progress is not None and time.monotonic() - last_report > 0.2:
            last_report = time.monotonic()
            progress(done, total)
    return sorted(result, key=lambda g: (-g.wasted, g.paths[0]))


def extra_copies(group, keep="oldest"):
    """Paths to remove so one copy stays: keep the "oldest", "newest" or "shortest" path."""
    def mtime(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0
    if keep == "oldest":
        keeper = min(group.paths, key=lambda p: (mtime(p), p))
    elif keep == "newest":
        keeper = max(group.paths, key=lambda p: (mtime(p), p))
    else:
        keeper = min(group.paths, key=lambda p: (len(p), p))
    return [p for p in group.paths if p != keeper]
