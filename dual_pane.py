"""
Dual-pane module for Shadows File Explorer.

This module provides FolderPane, a self-contained second folder view shown
beside the main view: its own path bar, back/up buttons, history and details
list. The main window decides what the pane's commands do; the pane only
reports what happened through signals.
"""
import os

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QAbstractItemView
from PyQt6.QtCore import Qt, QSize, QDir, pyqtSignal

from breadcrumb_bar import FixedBreadcrumbBar
from file_views import FileTreeView
from icons import FileIconProvider, ui_icon
from thumbnails import ThumbnailFileSystemModel
from utils import NavigationHistory, normalize_path


class FolderPane(QWidget):
    """A second folder pane for side-by-side browsing.

    Signals:
        open_file: A file was activated (path)
        files_dropped: Files were dropped on the pane (paths, destination, is_move)
        context_menu_requested: Right-click (paths, global position); paths is
            empty for a click on the background
        selection_changed: The selection changed
        close_requested: The close button was clicked
        location_changed: The pane now shows another folder (path)
        path_not_found: A typed path is not a folder (path)
    """

    open_file = pyqtSignal(str)
    files_dropped = pyqtSignal(list, str, bool)
    context_menu_requested = pyqtSignal(list, object)
    selection_changed = pyqtSignal()
    close_requested = pyqtSignal()
    location_changed = pyqtSignal(str)
    path_not_found = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("folder_pane")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.history = NavigationHistory()
        self.current_path = ""
        self.icon_color = "#c9ced6"
        self._buttons = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(2)
        self.back_button = self._button("back", "Back", self.go_back)
        self.up_button = self._button("up", "Up", self.go_up)
        header.addWidget(self.back_button)
        header.addWidget(self.up_button)
        self.breadcrumb_bar = FixedBreadcrumbBar()
        self.breadcrumb_bar.path_changed.connect(self.navigate)
        header.addWidget(self.breadcrumb_bar, 1)
        header.addWidget(self._button("close", "Close Second Pane (Ctrl+Shift+D)", self.close_requested.emit))
        layout.addLayout(header)

        # Own model, so the pane can show a different folder than the main view
        self.model = ThumbnailFileSystemModel(self)  # Thumbnails stay off; used for in-place rename
        self.icon_provider = FileIconProvider()
        self.model.setIconProvider(self.icon_provider)
        self.model.setRootPath("")

        self.view = FileTreeView()
        self.view.setModel(self.model)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.SelectedClicked)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.view.setRootIsDecorated(False)
        self.view.setItemsExpandable(False)
        self.view.setUniformRowHeights(True)
        self.view.setIconSize(QSize(18, 18))
        self.view.setColumnWidth(0, 240)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._show_context_menu)
        self.view.activated.connect(self._activated)
        self.view.files_dropped.connect(self.files_dropped.emit)
        self.view.selectionModel().selectionChanged.connect(lambda *_: self.selection_changed.emit())
        layout.addWidget(self.view, 1)

    def _button(self, icon_name, tooltip, slot):
        button = QToolButton()
        button.setIcon(ui_icon(icon_name, self.icon_color))
        button.setIconSize(QSize(16, 16))
        button.setFixedSize(28, 28)
        button.setToolTip(tooltip)
        button.clicked.connect(slot)
        self._buttons.append((button, icon_name))
        return button

    def set_icon_color(self, color):
        """Redraw the pane's button icons in the theme's icon color."""
        self.icon_color = color
        for button, name in self._buttons:
            button.setIcon(ui_icon(name, color))

    def set_show_hidden(self, show):
        filters = QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs
        if show:
            filters |= QDir.Filter.Hidden | QDir.Filter.System
        self.model.setFilter(filters)

    def set_active(self, active):
        """Mark the pane as the one commands apply to (styled by the theme)."""
        if self.property("active") != active:
            self.setProperty("active", active)
            self.style().unpolish(self)
            self.style().polish(self)

    def navigate(self, path, add_to_history=True):
        """Show a folder in the pane."""
        if not path or path == "pc":
            return
        path = normalize_path(path)
        if not os.path.isdir(path):
            self.path_not_found.emit(path)
            return
        if add_to_history:
            self.history.visit(path)
        self.current_path = path
        root = self.model.setRootPath(path)
        self.view.setRootIndex(root)
        self.view.clearSelection()
        self.breadcrumb_bar.set_path(path)
        self.back_button.setEnabled(self.history.can_go_back())
        parent = os.path.dirname(os.path.normpath(path))
        self.up_button.setEnabled(bool(parent) and os.path.normpath(parent) != os.path.normpath(path))
        self.location_changed.emit(path)

    def go_back(self):
        path = self.history.back()
        if path is not None:
            self.navigate(path, add_to_history=False)

    def go_up(self):
        parent = os.path.dirname(os.path.normpath(self.current_path))
        if parent and os.path.normpath(parent) != os.path.normpath(self.current_path):
            self.navigate(parent)

    def refresh(self):
        if self.current_path:
            self.navigate(self.current_path, add_to_history=False)

    def selected_paths(self):
        """Selected paths, one per row."""
        seen, paths = set(), []
        for index in self.view.selectionModel().selectedIndexes():
            if index.row() not in seen:
                seen.add(index.row())
                paths.append(self.model.filePath(index.siblingAtColumn(0)))
        return paths

    def _activated(self, index):
        path = self.model.filePath(index)
        if os.path.isdir(path):
            self.navigate(path)
        else:
            self.open_file.emit(path)

    def _show_context_menu(self, position):
        if not self.view.indexAt(position).isValid():
            self.view.clearSelection()
        self.context_menu_requested.emit(self.selected_paths(), self.view.viewport().mapToGlobal(position))
