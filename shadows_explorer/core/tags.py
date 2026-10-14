"""
Tags and color labels for Shadows File Explorer.

Any file or folder can carry tags ("Red", "Work", ...); each tag has a color.
Tags are kept by the app in one JSON file (the file system has no portable
place for them), and follow files that are moved or renamed in the app.
No Qt dependency.
"""
import json
import os
import tempfile

DEFAULT_TAGS = [
    ("Red", "#ef4444"), ("Orange", "#f97316"), ("Yellow", "#eab308"), ("Green", "#22c55e"),
    ("Blue", "#3b82f6"), ("Purple", "#a855f7"), ("Gray", "#9ca3af"),
]

# Offered when creating a tag
TAG_COLORS = [color for _, color in DEFAULT_TAGS] + ["#ec4899", "#14b8a6", "#78716c"]


def path_key(path):
    """How a path is stored: absolute, normalized, and lowercase on Windows."""
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


class TagStore:
    """Tag definitions (name -> color, in display order) and the tags of each path.

    Args:
        file_path: JSON file to load from and save to (None keeps everything in memory)
    """

    def __init__(self, file_path=None):
        self.file_path = file_path
        self.tags = dict(DEFAULT_TAGS)
        self.items = {}  # path_key -> {"path": path as given, "tags": [tag names]}
        self.revision = 0  # Bumped on every change, so views know to repaint
        if file_path and os.path.exists(file_path):
            self._load()

    # -------------------------- Storage --------------------------

    def _load(self):
        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        tags = data.get("tags")
        if isinstance(tags, list):
            self.tags = {name: color for name, color in (t for t in tags if isinstance(t, list) and len(t) == 2)
                         if isinstance(name, str) and isinstance(color, str)}
        items = data.get("items")
        if isinstance(items, dict):
            for key, item in items.items():
                if isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("tags"), list):
                    names = [n for n in item["tags"] if n in self.tags]
                    if names:
                        self.items[key] = {"path": item["path"], "tags": names}

    def save(self):
        """Write to the JSON file atomically (a crash never leaves half a file)."""
        self.revision += 1
        if not self.file_path:
            return
        folder = os.path.dirname(self.file_path)
        os.makedirs(folder, exist_ok=True)
        data = {"tags": [[name, color] for name, color in self.tags.items()], "items": self.items}
        fd, temp = tempfile.mkstemp(dir=folder, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(temp, self.file_path)
        except OSError:
            try:
                os.remove(temp)
            except OSError:
                pass

    # -------------------------- Reading --------------------------

    def find_tag(self, name):
        """The tag's exact name, matching case-insensitively, or None."""
        lowered = name.strip().lower()
        return next((tag for tag in self.tags if tag.lower() == lowered), None)

    def tags_for(self, path):
        """Tag names of path, in the tags' display order."""
        item = self.items.get(path_key(path))
        if not item:
            return []
        # list(): search threads call this while the UI may add a tag
        return [tag for tag in list(self.tags) if tag in item["tags"]]

    def colors_for(self, path):
        return [self.tags[tag] for tag in self.tags_for(path)]

    def paths_with(self, name):
        """Paths that have the tag (they may no longer exist)."""
        return sorted((item["path"] for item in self.items.values() if name in item["tags"]), key=str.lower)

    def counts(self):
        """Number of tagged paths per tag."""
        counts = dict.fromkeys(self.tags, 0)
        for item in self.items.values():
            for name in item["tags"]:
                counts[name] += 1
        return counts

    # -------------------------- Tagging --------------------------

    def set_tag(self, paths, name, on=True):
        """Add (on) or remove a tag on several paths."""
        if name not in self.tags:
            raise KeyError(name)
        for path in paths:
            key = path_key(path)
            names = [n for n in self.items.get(key, {}).get("tags", []) if n != name]
            if on:
                names.append(name)
            if names:
                self.items[key] = {"path": os.path.normpath(os.path.abspath(path)), "tags": names}
            else:
                self.items.pop(key, None)
        self.save()

    def toggle_tag(self, paths, name):
        """Add the tag to all paths, or remove it if they all have it already. Returns the new state."""
        on = not all(name in self.tags_for(path) for path in paths)
        self.set_tag(paths, name, on)
        return on

    def clear(self, paths):
        """Remove every tag from paths."""
        for path in paths:
            self.items.pop(path_key(path), None)
        self.save()

    # -------------------------- Tag definitions --------------------------

    def create_tag(self, name, color):
        """Add a tag; False if one with that name (any case) exists."""
        name = name.strip()
        if not name or self.find_tag(name):
            return False
        self.tags[name] = color
        self.save()
        return True

    def rename_tag(self, old, new):
        new = new.strip()
        existing = self.find_tag(new)
        if not new or old not in self.tags or (existing and existing != old):
            return False
        # Rebuild the dict to keep the tag's place in the order
        self.tags = {(new if name == old else name): color for name, color in self.tags.items()}
        for item in self.items.values():
            item["tags"] = [new if n == old else n for n in item["tags"]]
        self.save()
        return True

    def set_color(self, name, color):
        if name in self.tags:
            self.tags[name] = color
            self.save()

    def delete_tag(self, name):
        """Remove a tag and take it off every path."""
        self.tags.pop(name, None)
        for key in list(self.items):
            self.items[key]["tags"] = [n for n in self.items[key]["tags"] if n != name]
            if not self.items[key]["tags"]:
                del self.items[key]
        self.save()

    # -------------------------- Keeping up with file operations --------------------------

    def _keys_under(self, key):
        prefix = key.rstrip(os.sep) + os.sep
        return [k for k in self.items if k == key or k.startswith(prefix)]

    def move(self, pairs):
        """Files were moved or renamed: carry their tags (and those inside folders) along.

        Args:
            pairs: (old path, new path) tuples
        """
        changed = False
        moves = {}
        for old, new in pairs:
            old_key, new_key = path_key(old), path_key(new)
            new_path = os.path.normpath(os.path.abspath(new))
            if old == new:
                continue
            for key in self._keys_under(old_key):
                # A key is its path in lowercase (on Windows), so the lengths match
                rest = self.items[key]["path"][len(old_key):]
                moves[key] = (new_key + key[len(old_key):], new_path + rest)
        # Take everything out first, so swapped names don't overwrite each other
        taken = {key: self.items.pop(key) for key in moves}
        for key, item in taken.items():
            new_key, new_path = moves[key]
            self.items[new_key] = {"path": new_path, "tags": item["tags"]}
            changed = True
        if changed:
            self.save()

    def forget(self, paths):
        """Files were deleted: drop their tags (and those of anything inside)."""
        keys = [k for path in paths for k in self._keys_under(path_key(path))]
        for key in keys:
            self.items.pop(key, None)
        if keys:
            self.save()

    def prune_missing(self):
        """Drop tags of paths that no longer exist (e.g. deleted outside the app)."""
        missing = [key for key, item in self.items.items() if not os.path.exists(item["path"])]
        for key in missing:
            del self.items[key]
        if missing:
            self.save()
        return len(missing)
