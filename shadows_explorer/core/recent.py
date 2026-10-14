"""
Recent items module for Shadows File Explorer.

RecentItems remembers the files opened and folders visited in the app (most
recent first), for the "Recent" page in the sidebar. The lists are stored in
QSettings, or any object with value()/setValue(), so tests can use a dict.
"""
import json
import os
import time

from shadows_explorer.core.utils import paths_equal

MAX_FILES = 40
MAX_FOLDERS = 20


class RecentItems:
    """Most-recently-used files and folders.

    Each entry is {"path": ..., "time": unix timestamp}, newest first.
    """

    def __init__(self, settings):
        self.settings = settings
        self.files = self._load("recent_files")
        self.folders = self._load("recent_folders")

    def _load(self, key):
        raw = self.settings.value(key, "[]")
        try:
            entries = json.loads(raw) if isinstance(raw, str) else []
        except ValueError:
            return []
        return [e for e in entries if isinstance(e, dict) and isinstance(e.get("path"), str)]

    def _save(self):
        self.settings.setValue("recent_files", json.dumps(self.files))
        self.settings.setValue("recent_folders", json.dumps(self.folders))

    @staticmethod
    def _push(entries, path, limit):
        entries[:] = [e for e in entries if not paths_equal(e["path"], path)]
        entries.insert(0, {"path": path, "time": time.time()})
        del entries[limit:]

    def add_file(self, path):
        """Record that a file was opened."""
        self._push(self.files, os.path.abspath(path), MAX_FILES)
        self._save()

    def add_folder(self, path):
        """Record that a folder was visited."""
        self._push(self.folders, os.path.abspath(path), MAX_FOLDERS)
        self._save()

    def remove(self, path):
        """Forget one path (file or folder)."""
        self.files = [e for e in self.files if not paths_equal(e["path"], path)]
        self.folders = [e for e in self.folders if not paths_equal(e["path"], path)]
        self._save()

    def clear(self):
        """Forget everything."""
        self.files, self.folders = [], []
        self._save()

    def existing_files(self):
        """Recent file paths that still exist, newest first."""
        return [e["path"] for e in self.files if os.path.isfile(e["path"])]

    def existing_folders(self):
        """Recent folder paths that still exist, newest first."""
        return [e["path"] for e in self.folders if os.path.isdir(e["path"])]


def filter_pattern(text):
    """Wildcard pattern for the live filter: "rep" matches "*rep*".

    Text that already contains * or ? is used as a wildcard pattern itself.
    Square brackets are escaped so they match literally.

    Returns:
        str: A pattern for QFileSystemModel.setNameFilters / fnmatch, or "" for no filter
    """
    text = text.strip()
    if not text:
        return ""
    text = text.replace("[", "[[]")
    return text if ("*" in text or "?" in text) else f"*{text}*"
