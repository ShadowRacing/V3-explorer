"""
Thumbnail module for Shadows File Explorer.

ThumbnailFileSystemModel is a QFileSystemModel that shows picture thumbnails
instead of file icons, and checks names before renaming items in place. Images are decoded at a reduced size in background
threads (QImage is safe off the UI thread), cached in memory, and the view is
told to repaint each item when its thumbnail is ready.
"""
import os
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QObject, Qt, pyqtSignal

from shadows_explorer.core.utils import is_valid_filename, paths_equal
from PyQt6.QtGui import QColor, QFileSystemModel, QIcon, QImage, QImageReader, QPainter, QPixmap

THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".svg"}
MAX_IMAGE_BYTES = 80 * 1024 * 1024  # Skip enormous files


def load_thumbnail(path, size):
    """Decode an image scaled to fit size x size (runs in a worker thread).

    Returns:
        QImage: The thumbnail, or a null QImage if the file can't be read
    """
    try:
        if os.path.getsize(path) > MAX_IMAGE_BYTES:
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
    """Delivers thumbnails from worker threads to the UI thread."""
    loaded = pyqtSignal(str, object, QImage)


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

    def set_thumbnails_enabled(self, enabled):
        """Turn thumbnails on or off and repaint."""
        if enabled != self.thumbnails_enabled:
            self.thumbnails_enabled = enabled
            self.layoutChanged.emit()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if (self.thumbnails_enabled and role == Qt.ItemDataRole.DecorationRole
                and index.isValid() and index.column() == 0):
            thumbnail = self._thumbnail(index)
            if thumbnail is not None:
                return thumbnail
        return super().data(index, role)

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
        self._loader.loaded.emit(key[0], key, load_thumbnail(key[0], self.thumbnail_size))

    def _on_loaded(self, path, key, image):
        if self._closed:
            return
        self._pending.discard(key)
        if image.isNull():
            self._failed.add(key)
            return
        self._cache[key] = framed_icon(image, self.thumbnail_size)
        while len(self._cache) > self.CACHE_SIZE:
            self._cache.popitem(last=False)
        index = self.index(path)
        if index.isValid():
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])

    def shutdown(self):
        """Stop the worker threads (pending thumbnails are dropped)."""
        self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=True)

