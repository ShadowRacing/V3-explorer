"""
Disk usage dialog for Shadows File Explorer.

Scans a folder in the background and shows what takes up the space: a tree
sorted by size with a bar for each item's share of its parent, and a list of
the largest files. Double-clicking an item shows it in the main window.
"""
import os

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
                            QTreeWidget, QTreeWidgetItem, QStyledItemDelegate, QHeaderView,
                            QAbstractItemView)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter

from shadows_explorer.core.background import BackgroundJob
from shadows_explorer.core.disk_usage import ScanCancelled, largest_files, scan
from shadows_explorer.core.utils import format_size
from shadows_explorer.theme.icons import file_icon_for_path

NODE_ROLE = Qt.ItemDataRole.UserRole
SHARE_ROLE = Qt.ItemDataRole.UserRole + 1  # Share of the parent's size, 0..1
SORT_ROLE = Qt.ItemDataRole.UserRole + 2


class ShareBarDelegate(QStyledItemDelegate):
    """Draws an item's share of its parent as a bar with the percentage."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        share = index.data(SHARE_ROLE)
        if share is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect.adjusted(4, 6, -48, -6))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(128, 128, 128, 50))
        painter.drawRoundedRect(rect, 3, 3)
        filled = QRectF(rect)
        filled.setWidth(max(2.0, rect.width() * share))
        painter.setBrush(QColor("#dc2626") if share >= 0.5 else option.palette.highlight().color())
        painter.drawRoundedRect(filled, 3, 3)
        painter.setPen(option.palette.text().color())
        painter.drawText(option.rect.adjusted(0, 0, -4, 0),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{share * 100:.0f}%")
        painter.restore()


class SizeItem(QTreeWidgetItem):
    """Tree item that sorts by its numeric sort value instead of the display text."""

    def __lt__(self, other):
        column = self.treeWidget().sortColumn() if self.treeWidget() else 0
        mine, theirs = self.data(column, SORT_ROLE), other.data(column, SORT_ROLE)
        if mine is not None and theirs is not None:
            return mine < theirs
        return super().__lt__(other)


class DiskUsageDialog(QDialog):
    """Window showing what takes up space in a folder.

    Args:
        path: Folder to analyze
        show_path: Callback(path) that shows an item in the main window
    """

    def __init__(self, path, show_path, parent=None):
        super().__init__(parent)
        self.path = path
        self.show_path = show_path
        self.job = None
        self.setWindowTitle(f"Disk Usage - {os.path.basename(os.path.normpath(path)) or path}")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        self.summary_label = QLabel(f"Scanning {path}...")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.tabs = QTabWidget()
        self.tree = self._make_tree(["Name", "Size", "Share", "Files"])
        self.tree.itemExpanded.connect(self._fill_children)
        self.files_list = self._make_tree(["Name", "Size", "Folder"])
        self.files_list.setRootIsDecorated(False)
        self.tabs.addTab(self.tree, "Folders")
        self.tabs.addTab(self.files_list, "Largest files")
        layout.addWidget(self.tabs, 1)

        buttons = QHBoxLayout()
        buttons.addWidget(QLabel("Double-click an item to show it."), 1)
        self.rescan_button = QPushButton("Scan Again")
        self.rescan_button.clicked.connect(self.start_scan)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        buttons.addWidget(self.rescan_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.start_scan()

    def _make_tree(self, headers):
        tree = QTreeWidget()
        tree.setHeaderLabels(headers)
        tree.setSortingEnabled(True)
        tree.setUniformRowHeights(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tree.itemDoubleClicked.connect(self._show_item)
        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.setColumnWidth(1, 100)
        if len(headers) > 2:
            tree.setColumnWidth(2, 160 if headers[2] == "Share" else 260)
        if headers[2] == "Share":
            tree.setItemDelegateForColumn(2, ShareBarDelegate(tree))
        return tree

    def start_scan(self):
        """(Re)scan the folder in the background."""
        if self.job is not None:
            return
        self.tree.clear()
        self.files_list.clear()
        self.rescan_button.setEnabled(False)
        self.summary_label.setText(f"Scanning {self.path}...")
        self.job = BackgroundJob(lambda progress, cancel: scan(self.path, progress, cancel), self)
        self.job.progress.connect(lambda done, _: self.summary_label.setText(
            f"Scanning {self.path}... {done:,} files so far"))
        self.job.succeeded.connect(self._show_results)
        self.job.failed.connect(self._scan_failed)
        self.job.start()

    def _finish_job(self):
        self.job = None
        self.rescan_button.setEnabled(True)

    def _scan_failed(self, error):
        self._finish_job()
        if not isinstance(error, ScanCancelled):
            self.summary_label.setText(f"Could not scan {self.path}: {error}")

    def _show_results(self, root):
        self._finish_job()
        self.root = root
        folders = sum(1 for _ in self._walk_folders(root)) - 1
        self.summary_label.setText(
            f"<b>{format_size(root.size)}</b> in {root.files:,} files and {folders:,} folders - {self.path}")
        top = self._make_item(root, None)
        self.tree.addTopLevelItem(top)
        top.setExpanded(True)
        self.tree.sortItems(1, Qt.SortOrder.DescendingOrder)

        for node in largest_files(root):
            item = SizeItem([node.name, format_size(node.size), os.path.dirname(node.path)])
            item.setIcon(0, file_icon_for_path(node.path, False))
            item.setData(0, NODE_ROLE, node.path)
            item.setData(1, SORT_ROLE, node.size)
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.files_list.addTopLevelItem(item)
        self.files_list.sortItems(1, Qt.SortOrder.DescendingOrder)

    @staticmethod
    def _walk_folders(node):
        stack = [node]
        while stack:
            current = stack.pop()
            yield current
            stack.extend(c for c in current.children if c.is_dir)

    def _make_item(self, node, parent_size):
        item = SizeItem([node.name, format_size(node.size), "", f"{node.files:,}" if node.is_dir else ""])
        item.setIcon(0, file_icon_for_path(node.path, node.is_dir))
        item.setData(0, NODE_ROLE, node)
        item.setData(1, SORT_ROLE, node.size)
        item.setData(2, SORT_ROLE, node.size)
        item.setData(3, SORT_ROLE, node.files)
        if parent_size:
            item.setData(2, SHARE_ROLE, node.size / parent_size)
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if node.is_dir and node.children:
            # Children are added when the folder is expanded, so huge trees stay fast
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        return item

    def _fill_children(self, item):
        node = item.data(0, NODE_ROLE)
        if item.childCount() or not getattr(node, "children", None):
            return
        item.addChildren([self._make_item(child, node.size) for child in node.sorted_children()])

    def _show_item(self, item, column):
        data = item.data(0, NODE_ROLE)
        path = data.path if hasattr(data, "path") else data
        if path:
            self.show_path(path)

    def done(self, result):
        """Stop a running scan when the dialog closes."""
        if self.job is not None:
            self.job.cancel.set()
        super().done(result)
