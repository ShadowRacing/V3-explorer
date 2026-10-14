"""
Shared helpers for Shadows File Explorer.

Pure functions (no Qt widgets) so they can be unit tested without a display.
"""
import os
import platform

IS_WINDOWS = platform.system() == "Windows"


def format_size(size_bytes):
    """Format a byte count as a human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        str: Formatted size, e.g. "1.5 MB"
    """
    if size_bytes < 1024:
        return "1 byte" if size_bytes == 1 else f"{size_bytes} bytes"
    for unit in ("KB", "MB", "GB"):
        size_bytes /= 1024
        if size_bytes < 1024 or unit == "GB":
            return f"{size_bytes:.1f} {unit}"


def normalize_path(path, is_windows=IS_WINDOWS):
    """Normalize a navigation path.

    Bare drive letters ("C:", "C:/") become "C:\\" on Windows; all other
    paths keep their full depth.

    Args:
        path: Path to normalize
        is_windows: Treat the path as a Windows path

    Returns:
        str: Normalized path
    """
    if not path:
        return path
    if is_windows:
        if len(path) == 2 and path[1] == ":":
            return path + "\\"
        if len(path) == 3 and path[1] == ":" and path[2] in "/\\":
            return path[:2] + "\\"
        return path.replace("/", "\\")
    return path


def paths_equal(a, b):
    """Compare two paths, ignoring case on Windows and trailing separators."""
    if not a or not b:
        return False
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def is_within(path, parent):
    """Check whether path is parent or lies inside it.

    Unlike a plain startswith(), "/etcetera" is not inside "/etc".
    """
    path = os.path.normcase(os.path.abspath(path))
    parent = os.path.normcase(os.path.abspath(parent))
    try:
        return os.path.commonpath([path, parent]) == parent
    except ValueError:
        # Different drives on Windows
        return False


def unique_target_path(directory, name):
    """Return a path in directory for name that does not exist yet.

    "report.txt" becomes "report (1).txt", "report (2).txt", ...
    """
    target = os.path.join(directory, name)
    if not os.path.exists(target):
        return target
    base, ext = os.path.splitext(name)
    if os.path.isdir(target):
        base, ext = name, ""
    counter = 1
    while True:
        target = os.path.join(directory, f"{base} ({counter}){ext}")
        if not os.path.exists(target):
            return target
        counter += 1


def is_valid_filename(name):
    """Check that name can be used as a single file or folder name."""
    if not name or name in (".", "..") or name != name.strip():
        return False
    if "/" in name or "\\" in name or "\0" in name:
        return False
    if IS_WINDOWS:
        if any(c in name for c in '<>:"|?*') or name.endswith("."):
            return False
        reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
        if os.path.splitext(name)[0].upper() in reserved:
            return False
    return True


class NavigationHistory:
    """Browser-style back/forward history.

    The current location is always entries[index].
    """

    def __init__(self):
        self.entries = []
        self.index = -1

    @property
    def current(self):
        return self.entries[self.index] if self.index >= 0 else None

    def visit(self, path):
        """Record navigation to a new location, dropping any forward entries."""
        if self.current is not None and paths_equal(self.current, path):
            return
        del self.entries[self.index + 1:]
        self.entries.append(path)
        self.index = len(self.entries) - 1

    def can_go_back(self):
        return self.index > 0

    def can_go_forward(self):
        return self.index < len(self.entries) - 1

    def back(self):
        """Move back and return the new current path (or None)."""
        if not self.can_go_back():
            return None
        self.index -= 1
        return self.current

    def forward(self):
        """Move forward and return the new current path (or None)."""
        if not self.can_go_forward():
            return None
        self.index += 1
        return self.current
