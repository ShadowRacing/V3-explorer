"""
Disk usage module for Shadows File Explorer.

Measures how much space folders take, without Qt:
- folder_size(): total size and counts for one folder tree
- scan(): a full tree of sizes, for the disk usage breakdown
- largest_files(): the biggest files found by scan()

Symbolic links are never followed (they would count space twice or loop),
and unreadable folders are skipped. Both walks can be cancelled.
"""
import heapq
import os
import time
from dataclasses import dataclass, field


def folder_size(path, cancel_event=None):
    """Total size and file/folder counts of a directory tree.

    Args:
        path: Directory to measure
        cancel_event: Optional threading.Event that aborts the walk

    Returns:
        tuple: (total_bytes, file_count, folder_count)
    """
    total = files = folders = 0
    stack = [path]
    while stack:
        if cancel_event is not None and cancel_event.is_set():
            break
        try:
            with os.scandir(stack.pop()) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            folders += 1
                            stack.append(entry.path)
                        else:
                            files += 1
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total, files, folders


@dataclass
class Node:
    """A file or folder in a disk usage scan; folder sizes include everything inside."""
    name: str
    path: str
    is_dir: bool
    size: int = 0
    files: int = 0
    children: list = field(default_factory=list)

    def sorted_children(self):
        """Children, biggest first."""
        return sorted(self.children, key=lambda n: n.size, reverse=True)


class ScanCancelled(Exception):
    """Raised when a scan is cancelled."""


def scan(path, progress=None, cancel=None, progress_interval=0.2):
    """Build a tree of sizes under path.

    Args:
        path: Folder to scan
        progress: Optional callback(files_scanned, -1), called at most every progress_interval seconds
        cancel: Optional threading.Event; raises ScanCancelled when set

    Returns:
        Node: The root folder, with children and summed sizes
    """
    root = Node(os.path.basename(os.path.normpath(path)) or path, path, True)
    # Iterative depth-first walk: deep trees can't hit Python's recursion limit
    stack = [(root, False)]
    scanned = 0
    last_report = time.monotonic()
    while stack:
        node, children_done = stack.pop()
        if children_done:
            node.size = sum(child.size for child in node.children)
            node.files = sum(child.files if child.is_dir else 1 for child in node.children)
            continue
        if cancel is not None and cancel.is_set():
            raise ScanCancelled()
        stack.append((node, True))
        try:
            with os.scandir(node.path) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            child = Node(entry.name, entry.path, True)
                            stack.append((child, False))
                        else:
                            child = Node(entry.name, entry.path, False,
                                         entry.stat(follow_symlinks=False).st_size)
                            scanned += 1
                    except OSError:
                        continue
                    node.children.append(child)
        except OSError:
            continue
        if progress is not None and time.monotonic() - last_report >= progress_interval:
            last_report = time.monotonic()
            progress(scanned, -1)
    return root


def largest_files(root, count=50):
    """The count biggest files in a scanned tree, biggest first."""
    files = []
    stack = [root]
    while stack:
        node = stack.pop()
        for child in node.children:
            if child.is_dir:
                stack.append(child)
            else:
                files.append(child)
    return heapq.nlargest(count, files, key=lambda n: n.size)
