"""
Performance settings for Shadows File Explorer.

Every speed/memory trade-off the app makes, in one place: how many threads
thumbnails, search and folder sizes use, how much is cached, how big a file
may be before it is skipped, and how often things refresh. Presets fill them
in for slower or faster computers. No Qt dependency: values are loaded from
and saved to any object with value()/setValue() (QSettings in the app).
"""
import os
from dataclasses import dataclass, fields, replace


@dataclass
class Limit:
    """Allowed range of a number setting."""
    low: int
    high: int


# Ranges for the number settings; anything loaded from disk is clamped to them
LIMITS = {
    "thumbnail_threads": Limit(1, 8),
    "thumbnail_cache": Limit(50, 5000),
    "thumbnail_max_mb": Limit(1, 1000),
    "search_threads": Limit(0, 64),          # 0 = automatic (one per CPU core)
    "content_max_mb": Limit(1, 2048),
    "folder_size_threads": Limit(1, 8),
    "folder_refresh_ms": Limit(50, 5000),
    "drive_refresh_s": Limit(0, 300),        # 0 = only when asked
    "preview_text_kb": Limit(1, 2048),
    "preview_image_mb": Limit(1, 1000),
    "undo_steps": Limit(1, 500),
}


@dataclass
class PerformanceSettings:
    """All performance settings, with the app's defaults ("Balanced")."""
    # Thumbnails
    thumbnails: bool = True
    thumbnail_threads: int = 2
    thumbnail_cache: int = 600
    thumbnail_max_mb: int = 80
    # Search
    search_threads: int = 0
    search_hidden_folders: bool = False
    content_max_mb: int = 50
    # Folders and drives
    folder_size_threads: int = 1
    folder_refresh_ms: int = 300
    drive_refresh_s: int = 10
    # Preview panel
    preview_text_kb: int = 20
    preview_image_mb: int = 50
    preview_pdfs: bool = True
    # Memory
    undo_steps: int = 20

    SETTINGS_PREFIX = "performance/"

    # -------------------------- Derived values --------------------------

    @staticmethod
    def cpu_cores():
        return os.cpu_count() or 4

    def effective_search_threads(self):
        """Threads a search uses: the setting, or one per CPU core when automatic."""
        return self.search_threads or self.cpu_cores()

    # -------------------------- Storage --------------------------

    @classmethod
    def load(cls, settings):
        """Read the settings, falling back to defaults for anything missing or invalid."""
        values = {}
        for f in fields(cls):
            raw = settings.value(cls.SETTINGS_PREFIX + f.name, None)
            if raw is None:
                continue
            if f.type in (bool, "bool"):
                # QSettings may hand back "true"/"false" strings from INI files
                values[f.name] = raw if isinstance(raw, bool) else str(raw).lower() in ("true", "1", "yes")
            else:
                try:
                    values[f.name] = int(raw)
                except (TypeError, ValueError):
                    continue
        return cls(**values).clamped()

    def save(self, settings):
        for f in fields(self):
            settings.setValue(self.SETTINGS_PREFIX + f.name, getattr(self, f.name))

    def clamped(self):
        """A copy with every number inside its allowed range."""
        changes = {name: max(limit.low, min(limit.high, getattr(self, name))) for name, limit in LIMITS.items()}
        return replace(self, **changes)

    # -------------------------- Presets --------------------------

    def preset_name(self):
        """The preset these settings match, or "Custom"."""
        return next((name for name, values in PRESETS.items() if values == self), "Custom")


PRESETS = {
    "Balanced": PerformanceSettings(),
    # Older or slower computers: less work in the background, less memory
    "Light": PerformanceSettings(
        thumbnails=True, thumbnail_threads=1, thumbnail_cache=200, thumbnail_max_mb=20,
        search_threads=2, content_max_mb=10, folder_size_threads=1, folder_refresh_ms=800,
        drive_refresh_s=30, preview_text_kb=10, preview_image_mb=15, preview_pdfs=False, undo_steps=10),
    # Fast computers: more threads, bigger caches, fewer limits
    "Maximum": PerformanceSettings(
        thumbnails=True, thumbnail_threads=6, thumbnail_cache=3000, thumbnail_max_mb=400,
        search_threads=0, content_max_mb=500, folder_size_threads=4, folder_refresh_ms=150,
        drive_refresh_s=5, preview_text_kb=200, preview_image_mb=300, preview_pdfs=True, undo_steps=100),
}

PRESET_DESCRIPTIONS = {
    "Balanced": "Good for most computers (the default).",
    "Light": "For older or slower computers: fewer background threads, smaller caches, no PDF previews.",
    "Maximum": "For fast computers with plenty of memory: more threads, bigger caches, higher limits.",
    "Custom": "Your own mix of settings.",
}
