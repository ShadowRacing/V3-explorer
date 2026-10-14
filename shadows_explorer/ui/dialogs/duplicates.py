"""
Duplicate finder dialog for Shadows File Explorer.

Searches a folder for files with identical content (in the background), lists
each set of copies, and moves the copies the user ticks to the Recycle Bin.
At least one copy of every file always stays: removing all of them is refused.
"""
import os

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
                            QTreeWidgetItem, QSpinBox, QCheckBox, QHeaderView, QMessageBox, QMenu,
                            QAbstractItemView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from shadows_explorer.core.background import BackgroundJob
from shadows_explorer.core.duplicates import DuplicateScanCancelled, extra_copies, find_duplicates
from shadows_explorer.core.utils import format_size, format_timestamp
from shadows_explorer.theme.icons import file_icon_for_path

PATH_ROLE = Qt.ItemDataRole.UserRole
GROUP_ROLE = Qt.ItemDataRole.UserRole + 1


class DuplicatesDialog(QDialog):
    """Find duplicate files under a folder and recycle the extra copies.

    Args:
        folder: Folder to search (subfolders included)
        recycle: Callback(paths) -> list of paths that could NOT be recycled
        show_path: Callback(path) that shows a file in the main window
    """

    def __init__(self, folder, recycle, show_path, parent=None):
        super().__init__(parent)
        self.folder = folder
        self.recycle = recycle
        self.show_path = show_path
        self.job = None
        self.groups = []
        self.setWindowTitle(f"Find Duplicates - {os.path.basename(os.path.normpath(folder)) or folder}")
        self.resize(860, 600)

        layout = QVBoxLayout(self)

        options = QHBoxLayout()
        options.addWidget(QLabel(f"Search in: <b>{folder}</b>"), 1)
        options.addWidget(QLabel("Ignore files smaller than"))
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(0, 1024 * 1024)
        self.min_size_spin.setValue(1)
        self.min_size_spin.setSuffix(" KB")
        options.addWidget(self.min_size_spin)
        self.hidden_check = QCheckBox("Include hidden files")
        options.addWidget(self.hidden_check)
        self.scan_button = QPushButton("Search")
        self.scan_button.setProperty("class", "primary")
        self.scan_button.clicked.connect(self.start_scan)
        options.addWidget(self.scan_button)
        layout.addLayout(options)

        self.summary_label = QLabel("Click Search to look for files with identical content.")
        layout.addWidget(self.summary_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File", "Folder", "Modified"])
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(2, 140)
        self.tree.itemDoubleClicked.connect(self._show_item)
        self.tree.itemChanged.connect(lambda *_: self._update_selection_label())
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.tree, 1)

        actions = QHBoxLayout()
        actions.addWidget(QLabel("Tick copies to remove:"))
        for label, keep in (("Keep oldest", "oldest"), ("Keep newest", "newest"), ("Keep shortest path", "shortest")):
            button = QPushButton(label)
            button.setToolTip(f"Tick every copy except the {keep.replace('shortest', 'one with the shortest path')} "
                              f"in each set")
            button.clicked.connect(lambda checked=False, k=keep: self.auto_select(k))
            actions.addWidget(button)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(lambda: self._set_all_checked(False))
        actions.addWidget(clear_button)
        actions.addStretch()
        self.selection_label = QLabel()
        self.selection_label.setMinimumWidth(150)
        self.selection_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        actions.addWidget(self.selection_label)
        self.remove_button = QPushButton("Move to Recycle Bin")
        self.remove_button.clicked.connect(self.remove_checked)
        actions.addWidget(self.remove_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        actions.addWidget(close_button)
        layout.addLayout(actions)
        self._update_selection_label()

    # -------------------------- Scanning --------------------------

    def start_scan(self):
        if self.job is not None:
            return
        self.tree.clear()
        self.groups = []
        self.scan_button.setEnabled(False)
        self.summary_label.setText("Looking for files of the same size...")
        min_size = self.min_size_spin.value() * 1024
        include_hidden = self.hidden_check.isChecked()
        self.job = BackgroundJob(lambda progress, cancel: find_duplicates(
            [self.folder], min_size, include_hidden, progress, cancel), self)
        self.job.progress.connect(lambda done, total: self.summary_label.setText(
            f"Comparing contents... {done:,} of {total:,} candidate files"))
        self.job.succeeded.connect(self._show_results)
        self.job.failed.connect(self._scan_failed)
        self.job.start()

    def _finish_job(self):
        self.job = None
        self.scan_button.setEnabled(True)

    def _scan_failed(self, error):
        self._finish_job()
        if not isinstance(error, DuplicateScanCancelled):
            self.summary_label.setText(f"Search failed: {error}")

    def _show_results(self, groups):
        self._finish_job()
        self.groups = groups
        self.tree.blockSignals(True)
        bold = QFont()
        bold.setBold(True)
        for number, group in enumerate(groups):
            header = QTreeWidgetItem([f"{len(group.paths)} copies of {format_size(group.size)}  "
                                      f"({format_size(group.wasted)} could be freed)"])
            header.setFont(0, bold)
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for path in group.paths:
                try:
                    modified = format_timestamp(os.path.getmtime(path))
                except OSError:
                    modified = ""
                item = QTreeWidgetItem([os.path.basename(path), os.path.dirname(path), modified])
                item.setIcon(0, file_icon_for_path(path, False))
                item.setData(0, PATH_ROLE, path)
                item.setData(0, GROUP_ROLE, number)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                header.addChild(item)
            self.tree.addTopLevelItem(header)
            header.setFirstColumnSpanned(True)  # Only takes effect once the item is in the tree
            header.setExpanded(True)
        self.tree.blockSignals(False)
        if groups:
            wasted = sum(g.wasted for g in groups)
            copies = sum(len(g.paths) for g in groups)
            self.summary_label.setText(f"Found {len(groups):,} sets of duplicates ({copies:,} files). "
                                       f"Removing the extra copies would free <b>{format_size(wasted)}</b>.")
        else:
            self.summary_label.setText("No duplicate files found.")
        self._update_selection_label()

    # -------------------------- Selecting --------------------------

    def _file_items(self):
        for i in range(self.tree.topLevelItemCount()):
            header = self.tree.topLevelItem(i)
            for j in range(header.childCount()):
                yield header, header.child(j)

    def _set_all_checked(self, checked):
        self.tree.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for _, item in self._file_items():
            item.setCheckState(0, state)
        self.tree.blockSignals(False)
        self._update_selection_label()

    def auto_select(self, keep):
        """Tick every copy but one in each set ("oldest", "newest" or "shortest" is kept)."""
        to_remove = {path for group in self.groups for path in extra_copies(group, keep)}
        self.tree.blockSignals(True)
        for _, item in self._file_items():
            item.setCheckState(0, Qt.CheckState.Checked if item.data(0, PATH_ROLE) in to_remove
                               else Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self._update_selection_label()

    def checked_paths(self):
        return [item.data(0, PATH_ROLE) for _, item in self._file_items()
                if item.checkState(0) == Qt.CheckState.Checked]

    def _fully_checked_sets(self):
        """Sets where every copy is ticked (removing them would lose the file)."""
        sets = []
        for i in range(self.tree.topLevelItemCount()):
            header = self.tree.topLevelItem(i)
            children = [header.child(j) for j in range(header.childCount())]
            if children and all(c.checkState(0) == Qt.CheckState.Checked for c in children):
                sets.append(children[0].text(0))
        return sets

    def _update_selection_label(self):
        paths = self.checked_paths()
        size = 0
        for path in paths:
            try:
                size += os.path.getsize(path)
            except OSError:
                pass
        self.selection_label.setText(f"{len(paths)} ticked ({format_size(size)})" if paths else "")
        self.remove_button.setEnabled(bool(paths))

    # -------------------------- Removing --------------------------

    def remove_checked(self):
        """Move the ticked copies to the Recycle Bin, always keeping one copy of each file."""
        paths = self.checked_paths()
        if not paths:
            return
        lost = self._fully_checked_sets()
        if lost:
            QMessageBox.warning(self, "Keep at least one copy",
                                "Every copy is ticked for:\n\n" + "\n".join(lost[:10]) +
                                "\n\nUntick one copy of each so the file isn't lost.")
            return
        answer = QMessageBox.question(
            self, "Move to Recycle Bin",
            f"Move {len(paths)} duplicate file(s) to the Recycle Bin?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        failed = set(self.recycle(paths))
        self._drop_removed_items(set(paths) - failed)
        if failed:
            QMessageBox.warning(self, "Move to Recycle Bin",
                                f"{len(failed)} file(s) could not be removed and were left alone.")

    def _drop_removed_items(self, removed):
        """Remove deleted files from the list, and sets with only one file left."""
        for i in reversed(range(self.tree.topLevelItemCount())):
            header = self.tree.topLevelItem(i)
            for j in reversed(range(header.childCount())):
                if header.child(j).data(0, PATH_ROLE) in removed:
                    header.removeChild(header.child(j))
            if header.childCount() < 2:
                self.tree.takeTopLevelItem(i)
        self.summary_label.setText(f"Removed {len(removed)} duplicate file(s). "
                                   f"{self.tree.topLevelItemCount()} set(s) of duplicates left.")
        self._update_selection_label()

    # -------------------------- Misc --------------------------

    def _show_item(self, item, column):
        path = item.data(0, PATH_ROLE)
        if path:
            self.show_path(path)

    def _context_menu(self, position):
        item = self.tree.itemAt(position)
        path = item.data(0, PATH_ROLE) if item else None
        if not path:
            return
        menu = QMenu(self)
        menu.addAction("Show in Folder", lambda: self.show_path(path))
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def done(self, result):
        """Stop a running search when the dialog closes."""
        if self.job is not None:
            self.job.cancel.set()
        super().done(result)
