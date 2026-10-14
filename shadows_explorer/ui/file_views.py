"""
File view module for Shadows File Explorer.

This module provides the icon/list and details views used for browsing folders,
with drag and drop support, plus helpers for deciding whether a drop copies or
moves.
"""
import os

from PyQt6.QtWidgets import QAbstractItemView, QLineEdit, QListView, QTreeView
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from shadows_explorer.ui.tags import TagDotsDelegate


def local_paths_from_mime(mime):
    """Local file paths carried by drag-and-drop or clipboard data."""
    if mime is None or not mime.hasUrls():
        return []
    return [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]


def same_device(path_a, path_b):
    """Whether two paths are on the same drive / file system."""
    try:
        return os.stat(path_a).st_dev == os.stat(path_b).st_dev
    except OSError:
        return False


def should_move(sources, destination, modifiers):
    """Decide whether a drop moves (True) or copies (False), like Windows Explorer.

    Ctrl forces a copy and Shift forces a move. Otherwise items are moved
    within the same drive and copied between drives.

    Args:
        sources: Paths being dropped
        destination: Folder they are dropped on
        modifiers: Qt.KeyboardModifier flags held during the drop
    """
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        return False
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        return True
    return all(same_device(source, destination) for source in sources)


class RenameDelegate(TagDotsDelegate):
    """In-place rename editor that selects the name but not the extension; also draws tag dots."""
    
    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        if isinstance(editor, QLineEdit):
            name = editor.text()
            model = index.model()
            is_dir = hasattr(model, "isDir") and model.isDir(index)
            stem = os.path.splitext(name)[0] if not is_dir else name
            length = len(stem) if stem else len(name)
            # The view selects all text after this runs, so select on the next tick
            QTimer.singleShot(0, lambda: editor.setSelection(0, length))


class FileDropMixin:
    """Drag and drop behaviour shared by the folder views.

    The view must use a QFileSystemModel. Dropping on a folder item targets
    that folder; dropping on empty space targets the folder being shown.
    The subclass declares the signals (PyQt signals must live on the Qt class).
    """

    def _init_drag_drop(self):
        self.setItemDelegateForColumn(0, RenameDelegate(self))
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def _drop_target(self, pos):
        """Folder a drop at pos would land in."""
        model = self.model()
        index = self.indexAt(pos)
        if index.isValid() and model.isDir(index):
            return model.filePath(index)
        return model.filePath(self.rootIndex())

    def dragEnterEvent(self, event):
        if local_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not local_paths_from_mime(event.mimeData()):
            event.ignore()
            return
        target = self._drop_target(event.position().toPoint())
        is_move = should_move(local_paths_from_mime(event.mimeData()), target, event.modifiers())
        event.setDropAction(Qt.DropAction.MoveAction if is_move else Qt.DropAction.CopyAction)
        event.accept()

    def dropEvent(self, event):
        paths = local_paths_from_mime(event.mimeData())
        if not paths:
            event.ignore()
            return
        target = self._drop_target(event.position().toPoint())
        is_move = should_move(paths, target, event.modifiers())
        event.setDropAction(Qt.DropAction.MoveAction if is_move else Qt.DropAction.CopyAction)
        event.accept()
        self.files_dropped.emit(paths, target, is_move)

    def mouseReleaseEvent(self, event):
        # Middle-click on a folder opens it in a new tab
        if event.button() == Qt.MouseButton.MiddleButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid() and self.model().isDir(index):
                self.open_in_new_tab.emit(self.model().filePath(index))
                return
        super().mouseReleaseEvent(event)


class FileListView(FileDropMixin, QListView):
    """Icon and list view with drag and drop.

    Signals:
        files_dropped: Files were dropped (paths, destination folder, is_move)
        open_in_new_tab: A folder was middle-clicked (path)
    """

    files_dropped = pyqtSignal(list, str, bool)
    open_in_new_tab = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_drag_drop()
        # QListView's icon mode would otherwise let items be dragged around freely
        self.setMovement(QListView.Movement.Static)


class FileTreeView(FileDropMixin, QTreeView):
    """Details view with drag and drop.

    Signals:
        files_dropped: Files were dropped (paths, destination folder, is_move)
        open_in_new_tab: A folder was middle-clicked (path)
    """

    files_dropped = pyqtSignal(list, str, bool)
    open_in_new_tab = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_drag_drop()
