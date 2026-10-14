"""
File view module for Shadows File Explorer.

This module provides the icon/list and details views used for browsing folders,
with drag and drop support, plus helpers for deciding whether a drop copies or
moves.
"""
import os

from PyQt6.QtWidgets import (QAbstractItemView, QLineEdit, QListView, QStyle, QStyleOptionViewItem,
                             QTreeView)
from PyQt6.QtCore import QItemSelectionModel, QRect, Qt, QTimer, pyqtSignal

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


CHECK_SIZE = 16  # Item check boxes, like Explorer's "Item check boxes" option


class RenameDelegate(TagDotsDelegate):
    """In-place rename editor that selects the name but not the extension.

    Also draws tag dots, and the item's check box when the view shows them.
    """

    def _shift(self, view):
        """How far the item moves right to make room for its check box (0 in icon mode)."""
        if not getattr(view, "check_boxes", False) or view.is_icon_mode():
            return 0
        return CHECK_SIZE + 6

    def paint(self, painter, option, index):
        view = self.parent()
        if not getattr(view, "check_boxes", False):
            super().paint(painter, option, index)
            return
        shift = self._shift(view)
        if shift:
            # Background (selection, hover) across the whole cell, then the item beside the box
            background = QStyleOptionViewItem(option)
            self.initStyleOption(background, index)
            style = view.style()
            style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, background, painter, view)
            shifted = QStyleOptionViewItem(option)
            shifted.rect = option.rect.adjusted(shift, 0, 0, 0)
            shifted.state &= ~(QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver)
            if option.state & QStyle.StateFlag.State_Selected:
                # Keep the selected text color without drawing the highlight twice
                shifted.palette.setColor(shifted.palette.ColorRole.Text,
                                         option.palette.color(option.palette.ColorRole.HighlightedText))
            super().paint(painter, shifted, index)
        else:
            super().paint(painter, option, index)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        # Like Explorer: boxes appear on hover, and on every item once something is selected
        if selected or hovered or view.selectionModel().hasSelection():
            box = QStyleOptionViewItem(option)
            box.rect = view.check_rect(option.rect)
            box.state = QStyle.StateFlag.State_Enabled | (
                QStyle.StateFlag.State_On if selected else QStyle.StateFlag.State_Off)
            view.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck, box, painter, view)

    def updateEditorGeometry(self, editor, option, index):
        super().updateEditorGeometry(editor, option, index)
        shift = self._shift(self.parent())
        if shift:
            editor.setGeometry(editor.geometry().adjusted(shift, 0, 0, 0))
    
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

    check_boxes = False

    def _init_drag_drop(self):
        self.setItemDelegateForColumn(0, RenameDelegate(self))
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def is_icon_mode(self):
        return isinstance(self, QListView) and self.viewMode() == QListView.ViewMode.IconMode

    def set_check_boxes(self, enabled):
        """Show a check box on items; clicking it adds or removes the item from the selection."""
        self.check_boxes = enabled
        self.setMouseTracking(True)  # Hover state, so boxes appear under the mouse
        self.viewport().update()

    def check_rect(self, item_rect):
        """Where an item's check box is drawn, for the item's rectangle."""
        if self.is_icon_mode():
            return QRect(item_rect.left() + 4, item_rect.top() + 4, CHECK_SIZE, CHECK_SIZE)
        return QRect(item_rect.left() + 4, item_rect.center().y() - CHECK_SIZE // 2 + 1, CHECK_SIZE, CHECK_SIZE)

    def _check_box_at(self, pos):
        """The column-0 index whose check box is at pos, or None."""
        if not self.check_boxes:
            return None
        index = self.indexAt(pos)
        if not index.isValid():
            return None
        index = index.siblingAtColumn(0)
        if self.check_rect(self.visualRect(index)).adjusted(-3, -3, 3, 3).contains(pos):
            return index
        return None

    def mousePressEvent(self, event):
        index = self._check_box_at(event.position().toPoint()) if event.button() == Qt.MouseButton.LeftButton \
            else None
        if index is not None:
            flags = QItemSelectionModel.SelectionFlag.Toggle | QItemSelectionModel.SelectionFlag.Rows
            self.selectionModel().select(index, flags)
            self.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.viewport().update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        # A quick second click on a box toggles again instead of opening the item
        if self._check_box_at(event.position().toPoint()) is not None:
            self.mousePressEvent(event)
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        # Ctrl + mouse wheel zooms, as in Explorer
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y()
            if steps:
                self.zoom_requested.emit(1 if steps > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)

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
        zoom_requested: Ctrl + mouse wheel (+1 bigger, -1 smaller)
    """

    files_dropped = pyqtSignal(list, str, bool)
    open_in_new_tab = pyqtSignal(str)
    zoom_requested = pyqtSignal(int)

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
        zoom_requested: Ctrl + mouse wheel (+1 bigger, -1 smaller)
    """

    files_dropped = pyqtSignal(list, str, bool)
    open_in_new_tab = pyqtSignal(str)
    zoom_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_drag_drop()
