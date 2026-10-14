"""
Grouped view module for Shadows File Explorer.

GroupedFolderView lists a folder's items under collapsible group headers
("Today", "Pictures", "Large (128 MB - 1 GB)", ...). The groups themselves are
computed by grouping.py; this module only displays them.
"""
from PyQt6.QtWidgets import QAbstractItemView, QTreeView
from PyQt6.QtGui import QFont, QStandardItem, QStandardItemModel
from PyQt6.QtCore import QSize, Qt

from shadows_explorer.theme.icons import file_icon_for_path
from shadows_explorer.ui.search_results_model import PATH_ROLE
from shadows_explorer.core.utils import format_size, format_timestamp

HEADERS = ["Name", "Date Modified", "Type", "Size"]
GROUP_ROLE = Qt.ItemDataRole.UserRole + 2  # Group name on header rows


class GroupedFolderView(QTreeView):
    """Details-style list of folder items under group headers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.group_model = QStandardItemModel(0, len(HEADERS), self)
        self.group_model.setHorizontalHeaderLabels(HEADERS)
        self.setModel(self.group_model)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setUniformRowHeights(True)
        self.setIconSize(QSize(18, 18))
        self.setIndentation(12)
        self.setColumnWidth(0, 320)
        self.setColumnWidth(1, 150)
        self.setColumnWidth(2, 140)
        self._collapsed = set()  # Group names the user collapsed, kept across refreshes
        self.collapsed.connect(lambda index: self._collapsed.add(index.data(GROUP_ROLE)))
        self.expanded.connect(lambda index: self._collapsed.discard(index.data(GROUP_ROLE)))

    def populate(self, groups):
        """Show (group name, [Entry]) pairs; an empty group name means no headers."""
        self.group_model.removeRows(0, self.group_model.rowCount())
        bold = QFont()
        bold.setBold(True)
        for name, entries in groups:
            if name:
                header = QStandardItem(f"{name}  ({len(entries)})")
                header.setFont(bold)
                header.setData(name, GROUP_ROLE)
                header.setSelectable(False)
                header.setEditable(False)
                parent = header
                self.group_model.appendRow(header)
            else:
                parent = self.group_model.invisibleRootItem()
            for entry in entries:
                parent.appendRow(self._row(entry))
            if name:
                index = header.index()
                self.setFirstColumnSpanned(index.row(), index.parent(), True)
                self.setExpanded(index, name not in self._collapsed)

    @staticmethod
    def _row(entry):
        name_item = QStandardItem(file_icon_for_path(entry.path, entry.is_dir), entry.name)
        name_item.setData(entry.path, PATH_ROLE)
        date_item = QStandardItem(format_timestamp(entry.mtime))
        type_item = QStandardItem(entry.type_name)
        size_item = QStandardItem("" if entry.is_dir else format_size(entry.size))
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row = [name_item, date_item, type_item, size_item]
        for item in row:
            item.setEditable(False)
        return row

    def path_at(self, index):
        """The file path of the row at index, or None for a group header."""
        return index.siblingAtColumn(0).data(PATH_ROLE) if index.isValid() else None
