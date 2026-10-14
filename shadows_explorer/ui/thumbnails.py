"""
Thumbnail module for Shadows File Explorer.

ThumbnailFileSystemModel is a QFileSystemModel that shows picture thumbnails
instead of file icons, and checks names before renaming items in place. Images are decoded at a reduced size in background
threads (QImage is safe off the UI thread), cached in memory, and the view is
told to repaint each item when its thumbnail is ready.
"""
import os
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QObject, Qt, pyqtSignal

from shadows_explorer.core.disk_usage import folder_size
from shadows_explorer.core.utils import format_size, is_valid_filename, paths_equal
from PyQt6.QtGui import QColor, QFileSystemModel, QIcon, QImage, QImageReader, QPainter, QPixmap
from shadows_explorer.ui.tags import TAG_COLORS_ROLE

THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".svg"}
MAX_IMAGE_BYTES = 80 * 1024 * 1024  # Skip enormous files


def load_thumbnail(path, size, max_bytes=MAX_IMAGE_BYTES):
    """Decode an image scaled to fit size x size (runs in a worker thread).

    Returns:
        QImage: The thumbnail, or a null QImage if the file can't be read (or is over max_bytes)
    """
    try:
        if os.path.getsize(path) > max_bytes:
            return QImage()
    except OSError:
        return QImage()
    reader = QImageReader(path)
    reader.setAutoTransform(True)  # Respect EXIF rotation from cameras
    original = reader.size()
    if original.isValid() and (original.width() > size or original.height() > size):
        # Decoding at the target size is much faster than decoding and scaling
        reader.setScaledSize(original.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        return QImage()
    if image.width() > size or image.height() > size:
        image = image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    return image


def framed_icon(image, size):
    """Center a thumbnail on a square transparent canvas, so items line up."""
    canvas = QPixmap(size, size)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    x, y = (size - image.width()) // 2, (size - image.height()) // 2
    painter.drawImage(x, y, image)
    # A faint outline keeps light pictures visible on light backgrounds
    painter.setPen(QColor(128, 128, 128, 90))
    painter.drawRect(x, y, image.width() - 1, image.height() - 1)
    painter.end()
    return QIcon(canvas)


class _Loader(QObject):
    """Delivers thumbnails and folder sizes from worker threads to the UI thread."""
    loaded = pyqtSignal(str, object, QImage)
    size_loaded = pyqtSignal(str, object)


class ThumbnailFileSystemModel(QFileSystemModel):
    """A QFileSystemModel that shows picture thumbnails while enabled.

    Items can be renamed in place (the view's editor); names are checked
    first and problems reported through rename_failed instead of failing
    silently. Successful renames emit QFileSystemModel's fileRenamed.

    Signals:
        rename_failed: An in-place rename was refused (message)
    """

    rename_failed = pyqtSignal(str)
    CACHE_SIZE = 600

    def __init__(self, parent=None, size=128):
        super().__init__(parent)
        self.thumbnail_size = size
        self.thumbnails_enabled = False
        self._closed = False
        self._cache = OrderedDict()  # (path, mtime) -> QIcon, least recently used first
        self._failed = set()
        self._pending = set()
        self._pool = ThreadPoolExecutor(max_workers=2)
        self._loader = _Loader()
        self._loader.loaded.connect(self._on_loaded)
        self.setReadOnly(False)  # Allow renaming in place
        self.tag_store = None  # core.tags.TagStore, for tag dots (set by the window)
        self.thumbnails_allowed = True  # Performance setting; the view mode turns them on and off
        self.cache_size = self.CACHE_SIZE
        self.max_image_bytes = MAX_IMAGE_BYTES
        self._thumbnail_threads = 2
        self._size_threads = 1
        self.show_extensions = True

        # Folder sizes for the Size column (optional; a full walk per folder)
        self.folder_sizes_enabled = False
        self._folder_sizes = {}
        self._sizes_pending = set()
        self._size_cancel = threading.Event()
        self._size_pool = ThreadPoolExecutor(max_workers=1)
        self._loader.size_loaded.connect(self._on_size_loaded)

    def configure_performance(self, perf):
        """Apply core.performance.PerformanceSettings: threads, cache size and limits."""
        allowed_changed = perf.thumbnails != self.thumbnails_allowed
        self.thumbnails_allowed = perf.thumbnails
        self.cache_size = perf.thumbnail_cache
        self.max_image_bytes = perf.thumbnail_max_mb * 1024 * 1024
        self._failed.clear()  # A higher size limit may allow files that were skipped
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        if perf.thumbnail_threads != self._thumbnail_threads:
            old, self._pool = self._pool, ThreadPoolExecutor(max_workers=perf.thumbnail_threads)
            old.shutdown(wait=False, cancel_futures=True)
            self._pending.clear()
            self._thumbnail_threads = perf.thumbnail_threads
        if perf.folder_size_threads != self._size_threads:
            old, self._size_pool = self._size_pool, ThreadPoolExecutor(max_workers=perf.folder_size_threads)
            old.shutdown(wait=False, cancel_futures=True)
            self._sizes_pending.clear()
            self._size_threads = perf.folder_size_threads
        if allowed_changed and self.thumbnails_enabled:
            self.layoutChanged.emit()

    def clear_thumbnail_cache(self):
        """Forget every thumbnail (they are made again when shown)."""
        self._cache.clear()
        self._failed.clear()
        if self.thumbnails_enabled:
            self.layoutChanged.emit()

    def set_thumbnail_size(self, size):
        """Render thumbnails at size pixels (e.g. bigger when zoomed in)."""
        if size != self.thumbnail_size:
            self.thumbnail_size = size
            self._cache.clear()
            self._failed.clear()
            if self.thumbnails_enabled:
                self.layoutChanged.emit()

    def set_show_extensions(self, show):
        """Show or hide file name extensions ("report.pdf" or "report"), like Explorer's option."""
        if show != self.show_extensions:
            self.show_extensions = show
            self.layoutChanged.emit()

    def set_thumbnails_enabled(self, enabled):
        """Turn thumbnails on or off and repaint."""
        if enabled != self.thumbnails_enabled:
            self.thumbnails_enabled = enabled
            self.layoutChanged.emit()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role in (TAG_COLORS_ROLE, Qt.ItemDataRole.ToolTipRole) and self.tag_store is not None:
            if not index.isValid() or index.column() != 0:
                return None
            if role == TAG_COLORS_ROLE:
                return self.tag_store.colors_for(self.filePath(index))
            tags = self.tag_store.tags_for(self.filePath(index))
            if tags:
                return f"{self.fileName(index)}\nTags: {', '.join(tags)}"
        if (self.thumbnails_enabled and self.thumbnails_allowed and role == Qt.ItemDataRole.DecorationRole
                and index.isValid() and index.column() == 0):
            thumbnail = self._thumbnail(index)
            if thumbnail is not None:
                return thumbnail
        if (role == Qt.ItemDataRole.DisplayRole and not self.show_extensions and index.isValid()
                and index.column() == 0 and not self.isDir(index)):
            # Renaming still edits the full name (EditRole is untouched)
            stem, _ = os.path.splitext(self.fileName(index))
            return stem or self.fileName(index)
        if role == Qt.ItemDataRole.DisplayRole and index.isValid() and index.column() == 1:
            if not self.isDir(index):
                # Same "1.2 MB" style as the rest of the app (Qt would say "1.14 MiB")
                return format_size(self.size(index))
            if self.folder_sizes_enabled:
                return self._folder_size_text(self.filePath(index))
        return super().data(index, role)

    # -------------------------- Folder sizes --------------------------

    def set_folder_sizes_enabled(self, enabled):
        """Show folder sizes in the Size column (calculated in the background)."""
        if enabled != self.folder_sizes_enabled:
            self.folder_sizes_enabled = enabled
            self.layoutChanged.emit()

    def clear_folder_sizes(self):
        """Forget calculated sizes so they are measured again (e.g. on refresh)."""
        self._folder_sizes.clear()
        if self.folder_sizes_enabled:
            self.layoutChanged.emit()

    def _folder_size_text(self, path):
        size = self._folder_sizes.get(path)
        if size is not None:
            return format_size(size)
        if path not in self._sizes_pending:
            self._sizes_pending.add(path)
            self._size_pool.submit(self._measure_folder, path)
        return "Calculating..."

    def _measure_folder(self, path):
        # Worker thread
        total, _, _ = folder_size(path, self._size_cancel)
        if not self._size_cancel.is_set():
            self._loader.size_loaded.emit(path, total)

    def _on_size_loaded(self, path, total):
        if self._closed:
            return
        self._sizes_pending.discard(path)
        self._folder_sizes[path] = total
        index = self.index(path, 1)
        if index.isValid():
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid() or index.column() != 0:
            return super().setData(index, value, role)
        old_name = self.fileName(index)
        new_name = str(value).strip()
        if not new_name or new_name == old_name:
            return False
        if not is_valid_filename(new_name):
            self.rename_failed.emit(f"'{new_name}' is not a valid name.")
            return False
        old_path = self.filePath(index)
        target = os.path.join(os.path.dirname(old_path), new_name)
        # paths_equal allows case-only renames on case-insensitive file systems
        if os.path.lexists(target) and not paths_equal(target, old_path):
            self.rename_failed.emit(f"'{new_name}' already exists.")
            return False
        if not super().setData(index, new_name, role):
            self.rename_failed.emit(f"Could not rename '{old_name}'.")
            return False
        return True

    def _thumbnail(self, index):
        """Cached thumbnail for index, scheduling it if needed (None until ready)."""
        name = self.fileName(index)
        if os.path.splitext(name)[1].lower() not in THUMBNAIL_EXTENSIONS:
            return None
        info = self.fileInfo(index)
        if not info.isFile():
            return None
        key = (info.absoluteFilePath(), info.lastModified().toMSecsSinceEpoch())
        icon = self._cache.get(key)
        if icon is not None:
            self._cache.move_to_end(key)
            return icon
        if key not in self._pending and key not in self._failed:
            self._pending.add(key)
            self._pool.submit(self._load, key)
        return None

    def _load(self, key):
        # Worker thread: only QImage work here
        self._loader.loaded.emit(key[0], key, load_thumbnail(key[0], self.thumbnail_size, self.max_image_bytes))

    def _on_loaded(self, path, key, image):
        if self._closed:
            return
        self._pending.discard(key)
        if image.isNull():
            self._failed.add(key)
            return
        self._cache[key] = framed_icon(image, self.thumbnail_size)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        index = self.index(path)
        if index.isValid():
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])

    def shutdown(self):
        """Stop the worker threads (pending thumbnails and sizes are dropped)."""
        self._closed = True
        self._size_cancel.set()  # Stops a folder walk that is already running
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._size_pool.shutdown(wait=False, cancel_futures=True)

