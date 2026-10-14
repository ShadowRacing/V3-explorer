"""
Grouping module for Shadows File Explorer.

Plain functions (no Qt) that sort folder entries and split them into groups
the way Windows Explorer does: by type, by date modified ("Today",
"Last week", ...) or by size ("Small", "Large", ...).
"""
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from icons import file_kind

SORT_KEYS = ("name", "date", "size", "type")
GROUP_MODES = ("none", "type", "date", "size")

TYPE_GROUP_NAMES = {
    "folder": "Folders", "text": "Documents", "pdf": "Documents", "spreadsheet": "Documents",
    "presentation": "Documents", "image": "Pictures", "video": "Videos", "audio": "Music",
    "archive": "Archives", "code": "Code", "executable": "Programs", "file": "Other files",
}
TYPE_GROUP_ORDER = ["Folders", "Documents", "Pictures", "Videos", "Music", "Archives", "Code",
                    "Programs", "Other files"]
DATE_GROUP_ORDER = ["Today", "Yesterday", "Earlier this week", "Last week", "Earlier this month",
                    "Last month", "Earlier this year", "A long time ago", "In the future"]
SIZE_GROUPS = [  # (upper limit in bytes, name), checked in order
    (0, "Empty"), (16 * 1024, "Tiny (0 - 16 KB)"), (1024 ** 2, "Small (16 KB - 1 MB)"),
    (128 * 1024 ** 2, "Medium (1 - 128 MB)"), (1024 ** 3, "Large (128 MB - 1 GB)"),
    (4 * 1024 ** 3, "Huge (1 - 4 GB)"), (float("inf"), "Gigantic (> 4 GB)"),
]


@dataclass
class Entry:
    """One item in a folder listing."""
    name: str
    path: str
    is_dir: bool
    size: int
    mtime: float

    @property
    def type_name(self):
        if self.is_dir:
            return "Folder"
        ext = os.path.splitext(self.name)[1]
        return f"{ext[1:].upper()} File" if ext else "File"


def list_entries(folder, show_hidden=False):
    """Entries of a folder (hidden ones only when show_hidden)."""
    entries = []
    with os.scandir(folder) as items:
        for item in items:
            if not show_hidden and item.name.startswith("."):
                continue
            try:
                is_dir = item.is_dir()
                stats = item.stat()
            except OSError:
                continue
            entries.append(Entry(item.name, item.path, is_dir, 0 if is_dir else stats.st_size, stats.st_mtime))
    return entries


def sort_entries(entries, key="name", descending=False):
    """Sort entries, keeping folders before files like Explorer does."""
    key_functions = {
        "name": lambda e: e.name.lower(),
        "date": lambda e: e.mtime,
        "size": lambda e: e.size,
        "type": lambda e: (e.type_name.lower(), e.name.lower()),
    }
    ordered = sorted(entries, key=key_functions[key], reverse=descending)
    return [e for e in ordered if e.is_dir] + [e for e in ordered if not e.is_dir]


def date_group(mtime, today=None):
    """The date group name for a modification time."""
    today = today or date.today()
    day = datetime.fromtimestamp(mtime).date()
    if day > today:
        return "In the future"
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    start_of_week = today - timedelta(days=today.weekday())
    if day >= start_of_week:
        return "Earlier this week"
    if day >= start_of_week - timedelta(days=7):
        return "Last week"
    if day.year == today.year and day.month == today.month:
        return "Earlier this month"
    last_month_year, last_month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    if day.year == last_month_year and day.month == last_month:
        return "Last month"
    if day.year == today.year:
        return "Earlier this year"
    return "A long time ago"


def size_group(entry):
    if entry.is_dir:
        return "Folders"
    for limit, name in SIZE_GROUPS:
        if entry.size <= limit:
            return name
    return SIZE_GROUPS[-1][1]


def group_entries(entries, mode, today=None):
    """Split (already sorted) entries into ordered groups.

    Args:
        entries: Entry objects, in the order they should appear in each group
        mode: One of GROUP_MODES
        today: Date to treat as today (for tests)

    Returns:
        list: (group name, [entries]) pairs, empty groups left out
    """
    if mode == "none":
        return [("", list(entries))]
    if mode == "type":
        name_of = lambda e: TYPE_GROUP_NAMES["folder" if e.is_dir else file_kind(e.name)]
        order = TYPE_GROUP_ORDER
    elif mode == "date":
        name_of = lambda e: date_group(e.mtime, today)
        order = DATE_GROUP_ORDER
    elif mode == "size":
        name_of = size_group
        order = ["Folders"] + [name for _, name in SIZE_GROUPS]
    else:
        raise ValueError(f"Unknown group mode: {mode}")

    groups = {}
    for entry in entries:
        groups.setdefault(name_of(entry), []).append(entry)
    return [(name, groups[name]) for name in order if name in groups]
